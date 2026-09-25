# simulation.py
# A deep, event-based simulation engine inspired by Eastside Hockey Manager.
# Stage 1: Enhanced Event System & Shot Quality
# Stage 2: Advanced Possession & Zone Play
# Stage 3: Faceoffs & Special Situations
# Stage 4: Physical Play & Defensive Systems
# Stage 5: Goaltending Excellence

import random
import math
from enum import Enum
from game_classes import Team, Player, PlayerPosition
from player_archetypes import (
    get_archetype, complementarity, matchup_multiplier, get_tendency,
    ARCHETYPE_FIT, ARCHETYPE_TO_ROLE_NAME, attribute_value as _arch_attr,
)

class ShotType(Enum):
    WRIST_SHOT = "wrist_shot"
    SLAP_SHOT = "slap_shot"
    SNAP_SHOT = "snap_shot"
    TIP_IN = "tip_in"
    DEFLECTION = "deflection"
    REBOUND = "rebound"
    BACKHAND = "backhand"
    WRAPAROUND = "wraparound"
    ONE_TIMER = "one_timer"
    BREAKAWAY = "breakaway"

class ShotLocation(Enum):
    HIGH_SLOT = "high_slot"
    LOW_SLOT = "low_slot"
    LEFT_CIRCLE = "left_circle"
    RIGHT_CIRCLE = "right_circle"
    POINT = "point"
    LEFT_WING = "left_wing"
    RIGHT_WING = "right_wing"
    BEHIND_NET = "behind_net"
    CREASE = "crease"

class EventType(Enum):
    SHOT_ATTEMPT = "shot_attempt"
    SHOT_ON_GOAL = "shot_on_goal"
    BLOCKED_SHOT = "blocked_shot"
    MISSED_SHOT = "missed_shot"
    GOAL = "goal"
    SAVE = "save"
    FACEOFF = "faceoff"
    HIT = "hit"
    PENALTY = "penalty"
    TURNOVER = "turnover"

# Stage 2: Zone and Possession Classes
class Zone(Enum):
    DEFENSIVE_ZONE = "defensive_zone"
    NEUTRAL_ZONE = "neutral_zone"
    OFFENSIVE_ZONE = "offensive_zone"

class ZoneEntryType(Enum):
    CONTROLLED_CARRY = "controlled_carry"
    DUMP_IN = "dump_in"
    PASS_IN = "pass_in"
    CHIP_IN = "chip_in"

class PossessionType(Enum):
    CLEAN_POSSESSION = "clean_possession"
    LOOSE_PUCK = "loose_puck"
    BATTLE = "battle"
    TURNOVER = "turnover"

# Stage 3: Faceoff and Special Situations
class FaceoffZone(Enum):
    OFFENSIVE_ZONE = "offensive_zone"
    NEUTRAL_ZONE = "neutral_zone"
    DEFENSIVE_ZONE = "defensive_zone"

class FaceoffOutcome(Enum):
    CLEAN_WIN = "clean_win"
    DIRTY_WIN = "dirty_win"
    BATTLE = "battle"
    LOSS = "loss"

class SpecialSituation(Enum):
    EVEN_STRENGTH = "even_strength"
    POWER_PLAY = "power_play"
    PENALTY_KILL = "penalty_kill"
    FOUR_ON_FOUR = "four_on_four"
    THREE_ON_THREE = "three_on_three"
    SIX_ON_FIVE = "six_on_five"
    FIVE_ON_SIX = "five_on_six"
    FOUR_ON_THREE = "four_on_three"
    THREE_ON_FOUR = "three_on_four"

class PowerPlayFormation(Enum):
    UMBRELLA = "umbrella"
    OVERLOAD = "overload"
    SPREAD = "spread"
    CRASH_NET = "crash_net"

class PenaltyKillFormation(Enum):
    BOX = "box"
    DIAMOND = "diamond"
    TRIANGLE = "triangle"
    AGGRESSIVE = "aggressive"

# Stage 4: Physical Play & Defensive Systems
class HitType(Enum):
    BODY_CHECK = "body_check"
    POKE_CHECK = "poke_check"
    STICK_CHECK = "stick_check"
    BOARD_CHECK = "board_check"
    CLEAN_HIT = "clean_hit"
    CHARGING = "charging"
    BOARDING = "boarding"

class HitResult(Enum):
    SUCCESSFUL = "successful"
    MISSED = "missed"
    TURNOVER_CAUSED = "turnover_caused"
    PENALTY_DRAWN = "penalty_drawn"
    INJURY_CAUSED = "injury_caused"

class DefensiveAction(Enum):
    STICK_LIFT = "stick_lift"
    BODY_POSITION = "body_position"
    ACTIVE_STICK = "active_stick"
    SHOT_BLOCK = "shot_block"
    PASS_INTERCEPTION = "pass_interception"
    FORECHECKING = "forechecking"
    BACKCHECKING = "backchecking"

class TurnoverType(Enum):
    TAKEAWAY = "takeaway"
    GIVEAWAY = "giveaway"
    FORCED_ERROR = "forced_error"
    UNFORCED_ERROR = "unforced_error"
    STRIP = "strip"
    INTERCEPTION = "interception"

class DefensiveSystem(Enum):
    ZONE_COVERAGE = "zone_coverage"
    MAN_TO_MAN = "man_to_man"
    HYBRID = "hybrid"
    AGGRESSIVE_FORECHECK = "aggressive_forecheck"
    DEFENSIVE_SHELL = "defensive_shell"
    NEUTRAL_ZONE_TRAP = "neutral_zone_trap"

# Stage 5: Goaltending Excellence
class SaveType(Enum):
    GLOVE_SAVE = "glove_save"
    BLOCKER_SAVE = "blocker_save"
    PAD_SAVE = "pad_save"
    STICK_SAVE = "stick_save"
    CHEST_SAVE = "chest_save"
    MASK_SAVE = "mask_save"
    DESPERATION_SAVE = "desperation_save"
    DIVING_SAVE = "diving_save"

class GoalType(Enum):
    FIVE_HOLE = "five_hole"
    TOP_SHELF = "top_shelf"
    LOW_GLOVE = "low_glove"
    LOW_BLOCKER = "low_blocker"
    HIGH_GLOVE = "high_glove"
    HIGH_BLOCKER = "high_blocker"
    SCREEN_SHOT = "screen_shot"
    DEFLECTION = "deflection"
    REBOUND = "rebound"

class GoaltenderPosition(Enum):
    IN_NET = "in_net"
    CHALLENGING = "challenging"
    DEEP_NET = "deep_net"
    AGGRESSIVE = "aggressive"
    BUTTERFLY = "butterfly"
    STAND_UP = "stand_up"
    HYBRID = "hybrid"

class ReboundControl(Enum):
    ABSORBED = "absorbed"
    CONTROLLED = "controlled"
    WEAK_REBOUND = "weak_rebound"
    DANGEROUS_REBOUND = "dangerous_rebound"
    DEFLECTED_AWAY = "deflected_away"
    KICKED_OUT = "kicked_out"

class GoaltenderStyle(Enum):
    BUTTERFLY = "butterfly"
    HYBRID = "hybrid"
    STAND_UP = "stand_up"
    REACTIONARY = "reactionary"
    POSITIONAL = "positional"

# ===== STAGE 6: ADVANCED PLAYER CHEMISTRY & LINE COMBINATIONS =====

# ===== STAGE 7: MICRO-EVENTS & GAME FLOW =====

# ===== STAGE 8: ADVANCED ANALYTICS INTEGRATION =====

class MicroEventType(Enum):
    # Puck control micro-events
    PUCK_PICKUP = "puck_pickup"
    PUCK_LOSE = "puck_lose"
    PUCK_BATTLE = "puck_battle"
    PUCK_FLIP = "puck_flip"
    PUCK_CLEAR = "puck_clear"
    
    # Movement micro-events
    PLAYER_ACCELERATION = "player_acceleration"
    PLAYER_DECELERATION = "player_deceleration"
    PLAYER_TURN = "player_turn"
    PLAYER_STOP = "player_stop"
    POSITION_CHANGE = "position_change"
    
    # Tactical micro-events
    LINE_CHANGE = "line_change"
    FORMATION_SHIFT = "formation_shift"
    PRESSURE_APPLICATION = "pressure_application"
    SUPPORT_MOVEMENT = "support_movement"
    DEFENSIVE_POSITIONING = "defensive_positioning"
    
    # Communication micro-events
    PLAYER_COMMUNICATION = "player_communication"
    COACH_INSTRUCTION = "coach_instruction"
    CAPTAIN_LEADERSHIP = "captain_leadership"
    
    # Physical micro-events
    CONTACT_INITIATED = "contact_initiated"
    CONTACT_AVOIDED = "contact_avoided"
    BALANCE_LOST = "balance_lost"
    BALANCE_RECOVERED = "balance_recovered"
    
    # Mental micro-events
    CONFIDENCE_BOOST = "confidence_boost"
    PRESSURE_FELT = "pressure_felt"
    FOCUS_GAINED = "focus_gained"
    MOMENTUM_SHIFT = "momentum_shift"

class GameMomentum(Enum):
    HEAVILY_FAVORING_HOME = "heavily_favoring_home"  # +3
    FAVORING_HOME = "favoring_home"                  # +2
    SLIGHTLY_FAVORING_HOME = "slightly_favoring_home" # +1
    NEUTRAL = "neutral"                              # 0
    SLIGHTLY_FAVORING_AWAY = "slightly_favoring_away" # -1
    FAVORING_AWAY = "favoring_away"                  # -2
    HEAVILY_FAVORING_AWAY = "heavily_favoring_away"  # -3

class GameFlow(Enum):
    VERY_SLOW = "very_slow"          # 0.7x event frequency
    SLOW = "slow"                    # 0.85x event frequency
    NORMAL = "normal"                # 1.0x event frequency
    FAST = "fast"                    # 1.15x event frequency
    VERY_FAST = "very_fast"          # 1.3x event frequency
    FRANTIC = "frantic"              # 1.5x event frequency

class PressureLevel(Enum):
    MINIMAL = "minimal"              # 0-20%
    LOW = "low"                      # 21-40%
    MODERATE = "moderate"            # 41-60%
    HIGH = "high"                    # 61-80%
    INTENSE = "intense"              # 81-100%

class ChemistryType(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    NEUTRAL = "neutral"
    POOR = "poor"
    TERRIBLE = "terrible"

class LineRole(Enum):
    PRIMARY_SCORER = "primary_scorer"
    PLAYMAKER = "playmaker"
    GRINDER = "grinder"
    DEFENSIVE_FORWARD = "defensive_forward"
    POWER_FORWARD = "power_forward"
    SHUTDOWN_DEFENDER = "shutdown_defender"
    OFFENSIVE_DEFENDER = "offensive_defender"
    TWO_WAY_DEFENDER = "two_way_defender"
    ENFORCER = "enforcer"
    PENALTY_KILLER = "penalty_killer"
    POWER_PLAY_SPECIALIST = "power_play_specialist"

class CoachingStyle(Enum):
    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"
    BALANCED = "balanced"
    OFFENSIVE = "offensive"
    PHYSICAL = "physical"
    SPEED_GAME = "speed_game"
    POSSESSION = "possession"

class LineChemistry(Enum):
    DOMINANT = "dominant"        # 95-100% chemistry
    EXCELLENT = "excellent"     # 85-94% chemistry
    GOOD = "good"              # 70-84% chemistry
    AVERAGE = "average"        # 55-69% chemistry
    POOR = "poor"             # 40-54% chemistry
    DYSFUNCTIONAL = "dysfunctional"  # Below 40% chemistry

class TacticalSystem(Enum):
    # Offensive Systems
    CYCLE_GAME = "cycle_game"
    RUSH_OFFENSE = "rush_offense"
    POWER_PLAY_UMBRELLA = "power_play_umbrella"
    OVERLOAD = "overload"
    
    # Defensive Systems  
    NEUTRAL_ZONE_TRAP = "neutral_zone_trap"
    AGGRESSIVE_FORECHECK = "aggressive_forecheck"
    CONSERVATIVE_DEFENSE = "conservative_defense"
    PENALTY_KILL_BOX = "penalty_kill_box"
    
    # Special Situations
    FOUR_ON_FOUR_OPEN = "four_on_four_open"
    THREE_ON_THREE_CHAOS = "three_on_three_chaos"

# ===== STAGE 8: ADVANCED ANALYTICS ENUMS =====

class AnalyticsModel(Enum):
    EXPECTED_GOALS = "expected_goals"
    WIN_PROBABILITY = "win_probability"
    PLAYER_IMPACT = "player_impact"
    LINEUP_OPTIMIZATION = "lineup_optimization"
    GAME_SCRIPT = "game_script"
    MATCHUP_ANALYSIS = "matchup_analysis"
    MOMENTUM_TRACKING = "momentum_tracking"
    CLUTCH_FACTOR = "clutch_factor"

class PredictionType(Enum):
    SHOT_OUTCOME = "shot_outcome"
    SCORING_CHANCE = "scoring_chance"
    TURNOVER_RISK = "turnover_risk"
    PENALTY_LIKELIHOOD = "penalty_likelihood"
    LINE_CHANGE_OPTIMAL = "line_change_optimal"
    GOALIE_PULL_TIMING = "goalie_pull_timing"
    FORMATION_COUNTER = "formation_counter"
    MOMENTUM_SHIFT = "momentum_shift"

class PerformanceMetric(Enum):
    GOALS_ABOVE_EXPECTED = "goals_above_expected"
    SAVES_ABOVE_EXPECTED = "saves_above_expected"
    POINTS_ABOVE_REPLACEMENT = "points_above_replacement"
    WAR = "wins_above_replacement"
    CLUTCH_RATING = "clutch_rating"
    DEFENSIVE_IMPACT = "defensive_impact"
    OFFENSIVE_ZONE_IMPACT = "offensive_zone_impact"
    SPECIAL_TEAMS_VALUE = "special_teams_value"

class TrendDirection(Enum):
    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"
    VOLATILE = "volatile"
    HOT_STREAK = "hot_streak"
    COLD_STREAK = "cold_streak"
    BREAKOUT_CANDIDATE = "breakout_candidate"
    REGRESSION_CANDIDATE = "regression_candidate"

class AnalyticsLevel(Enum):
    BASIC = "basic"           # Traditional stats
    INTERMEDIATE = "intermediate"  # Shot attempts, zone time
    ADVANCED = "advanced"     # Expected goals, WAR
    ELITE = "elite"          # Machine learning models
    PROPRIETARY = "proprietary"  # Custom algorithms

class GameSim:
    """
    Manages the state and logic for simulating a single hockey game.
    Stage 1: Enhanced with detailed shot tracking, quality metrics, and Corsi events.
    Stage 2: Advanced possession tracking, zone play, and fatigue system.
    Stage 3: Detailed faceoffs, special situations, and power play systems.
    Stage 4: Physical play mechanics, defensive systems, and turnover tracking.
    Stage 5: Advanced goaltending mechanics, save types, and positioning systems.
    """
    def __init__(self, home_team: Team, away_team: Team, is_playoff: bool = False):
        self.home_team = home_team
        self.away_team = away_team
        self.is_playoff = is_playoff
        self.home_score = 0
        self.away_score = 0
        self.period = 1
        self.clock = 1200  # 20 minutes in seconds
        self._period_length = 1200  # for event_log elapsed timestamps
        self.game_log = []
        self.notable_events = []
        self.event_log = []  # Structured event dicts (GOAL_ADVANCED, SAVE_ADVANCED, ...)

        # Play-by-play visualizer hooks (additive; zero overhead when unused).
        # Listeners are callables receiving one event dict each.
        self.pbp_listeners = []
        # Sudden-death OT bookkeeping (set by _handle_overtime)
        self._ot_sudden_death = False
        self._ot_start_score = None
        
        self.home_penalties = []
        self.away_penalties = []
        
        self.home_on_ice = []
        self.away_on_ice = []
        
        # Stage 2: Zone and possession tracking
        self.current_zone = Zone.NEUTRAL_ZONE
        self.possession_team = None
        self.possession_player = None
        self.possession_type = PossessionType.CLEAN_POSSESSION
        self.zone_time = 0  # Time spent in current zone
        self.possession_time = 0  # Time current player has had possession
        
        # Stage 2: Fatigue tracking
        self.player_fatigue = {}
        self.line_change_timer = 0
        
        # Stage 3: Special situations and faceoffs
        self.current_situation = SpecialSituation.EVEN_STRENGTH
        self.faceoff_zone = FaceoffZone.NEUTRAL_ZONE
        self.power_play_formation = PowerPlayFormation.UMBRELLA
        self.penalty_kill_formation = PenaltyKillFormation.BOX
        
        # Stage 4: Physical play and defensive systems
        self.current_defensive_system = DefensiveSystem.ZONE_COVERAGE
        self.hit_tracking = {'successful_hits': 0, 'missed_hits': 0, 'penalties_from_hits': 0}
        self.physical_intensity = 1.0  # Base physical play intensity
        self.defensive_pressure = 1.0  # Current defensive pressure level
        
        # Stage 5: Goaltending systems
        self.goaltender_fatigue = {}  # Track goalie fatigue
        self.goaltender_positioning = {}  # Track goalie positioning
        self.expected_goals = {}  # team_name -> xG; track expected goals for GSAx calculation
        self.save_quality_tracking = {}  # Track save difficulty and quality
        
        # Stage 6: Player chemistry and line combinations
        self.line_chemistry = {}  # line_id -> chemistry_rating (0-100)
        self.chemistry_bonuses = {}  # player_id -> current_bonus
        self.coaching_adjustments = {}  # situation -> adjustment_factor
        self.role_performance = {}  # player_id -> role_effectiveness
        self.line_matchups = {}  # tracking line vs line performance
        self.tactical_system = TacticalSystem.CYCLE_GAME  # Current team system
        self.line_fatigue = {}  # line_id -> fatigue_level
        self.chemistry_evolution = {}  # Track how chemistry changes over time
        
        # Stage 7: Micro-events and game flow
        self.momentum = GameMomentum.NEUTRAL  # Current game momentum
        self.game_flow = GameFlow.NORMAL  # Current pace of play
        self.pressure_level = PressureLevel.MODERATE  # Current pressure level
        self.situational_context = SituationalContext.GAME_OPENING
        self.micro_events = []  # Detailed micro-event log
        self.momentum_history = []  # Track momentum changes over time
        self.pressure_zones = {}  # Track pressure by ice zone
        self.transition_sequences = []  # Track complex event sequences
        self.contextual_adjustments = {}  # Situation-specific performance changes
        self.flow_multipliers = {}  # Game flow impact on different actions
        
        # Stage 8: Advanced analytics integration
        self.analytics_engine = {}  # Real-time analytics calculations
        self.prediction_models = {}  # Predictive modeling systems
        self.performance_trends = {}  # Player performance tracking over time
        self.expected_goals_model = {}  # xG calculations and tracking
        self.win_probability = 0.5  # Real-time win probability
        self.player_war_tracking = {}  # Wins Above Replacement tracking
        self.clutch_situations = []  # High-leverage situation tracking
        self.game_script_analysis = {}  # How game is unfolding vs expectations
        self.lineup_analytics = {}  # Line combination effectiveness tracking
        self.momentum_predictors = {}  # Momentum shift prediction variables
        self.situational_analytics = {}  # Context-aware performance metrics
        self.real_time_adjustments = {}  # Analytics-driven coaching adjustments
        
        # Enhanced stats tracking for Stages 1, 2 & 3
        self.game_stats = {p.id: {
            'g': 0, 'a': 0, 'player': p,
            # Shot tracking (Stage 1)
            'shots_on_goal': 0,
            'shot_attempts': 0,
            'blocked_shots': 0,
            'missed_shots': 0,
            'shots_blocked': 0,
            # Shot quality (Stage 1)
            'high_danger_shots': 0,
            'medium_danger_shots': 0,
            'low_danger_shots': 0,
            'shot_distance_total': 0,
            'rebounds_created': 0,
            'rebounds_scored': 0,
            # Corsi events (Stage 1)
            'corsi_for': 0,
            'corsi_against': 0,
            # Zone play (Stage 2)
            'zone_entries': 0,
            'zone_exits': 0,
            'controlled_zone_entries': 0,
            'dump_ins': 0,
            'zone_time_offensive': 0,
            'zone_time_defensive': 0,
            'zone_starts_offensive': 0,
            'zone_starts_defensive': 0,
            # Possession (Stage 2)
            'possession_time': 0,
            'possession_gains': 0,
            'possession_losses': 0,
            'puck_battles_won': 0,
            'puck_battles_lost': 0,
            # Faceoffs (Stage 3)
            'faceoffs_taken': 0,
            'faceoffs_won': 0,
            'faceoffs_lost': 0,
            'faceoffs_neutral_zone': 0,
            'faceoffs_offensive_zone': 0,
            'faceoffs_defensive_zone': 0,
            # Special teams (Stage 3)
            'power_play_goals': 0,
            'power_play_assists': 0,
            'power_play_shots': 0,
            'penalty_kill_goals': 0,
            'penalty_kill_assists': 0,
            'short_handed_goals': 0,
            'power_play_time': 0,
            'penalty_kill_time': 0,
            # Physical play (Stage 4)
            'hits': 0,
            'hits_taken': 0,
            'takeaways': 0,
            'giveaways': 0,
            'blocked_shots_by': 0,  # Shots blocked by this player
            'shots_blocked_against': 0,  # This player's shots blocked
            'checks': 0,
            'defensive_plays': 0,
            'turnovers_forced': 0,
            'turnovers_committed': 0,
            'physical_penalties': 0,
            # Goaltending (Stage 5)
            'saves': 0,
            'goals_against': 0,
            'shots_against': 0,
            'save_percentage': 0.0,
            'goals_saved_above_expected': 0.0,
            'high_danger_saves': 0,
            'medium_danger_saves': 0,
            'low_danger_saves': 0,
            'glove_saves': 0,
            'blocker_saves': 0,
            'pad_saves': 0,
            'stick_saves': 0,
            'desperation_saves': 0,
            'rebounds_allowed': 0,
            'rebounds_controlled': 0,
            'shutouts': 0,
            'quality_starts': 0,
            # Chemistry and line combinations (Stage 6)
            'chemistry_bonus': 0.0,
            'chemistry_goals': 0,
            'chemistry_assists': 0,
            'chemistry_rating': 50.0,  # Start neutral
            'role_effectiveness': 0.0,
            'line_matching_advantage': 0,
            'coaching_bonus': 0.0,
            'tactical_plays_successful': 0,
            'tactical_plays_attempted': 0,
            'linemate_synergy': {},  # Track chemistry with specific players
            'system_fitness': 0.0,  # How well player fits current tactical system
            
            # Micro-events and game flow (Stage 7)
            'momentum_events': 0,
            'pressure_applied': 0.0,
            'pressure_withstood': 0.0,
            'micro_battles_won': 0,
            'micro_battles_lost': 0,
            'transition_success': 0,
            'transition_failures': 0,
            'situational_awareness': 0.0,
            'clutch_performance': 0.0,
            'flow_adaptation': 0.0,  # How well player adapts to game flow
            'communication_events': 0,
            'leadership_moments': 0,
            
            # Advanced analytics (Stage 8)
            'expected_goals': 0.0,
            'goals_above_expected': 0.0,
            'war': 0.0,  # Wins Above Replacement
            'par': 0.0,  # Points Above Replacement
            'clutch_factor': 0.0,
            'situational_impact': {},  # Impact in different situations
            'predictive_performance': 0.0,  # How well performance matches predictions
            'analytics_rating': 0.0,  # Overall analytics-based rating
            'trend_direction': TrendDirection.STABLE,
            'breakout_probability': 0.0,
            'regression_risk': 0.0,
            'optimal_usage': {},  # Analytics-suggested usage patterns
            'real_time_adjustments': 0,
            
            # Stage 9 stats - Situational Awareness & AI
            'ai_decisions_influenced': 0,
            'situational_context_success': 0.0,
            'adaptive_performance': 0.0,
            'context_aware_rating': 0.0,
            'ai_coaching_impact': 0.0,
            'decision_confidence_affected': 0.0,
            'intelligent_usage_optimization': 0.0,
            'situational_adaptation_speed': 0.0,
            'ai_learning_contribution': 0.0,
            'context_recognition_accuracy': 0.0,
            'strategic_awareness_impact': 0.0,
            'momentum_ai_response': 0.0,
            'game_state_awareness': 0.0,
            
            # Stage 10 stats - Machine Learning & Performance Prediction
            'development_prediction': DevelopmentPhase.DEVELOPING,
            'performance_trajectory': 0.0,
            'injury_risk_score': 0.0,
            'career_projection_confidence': 0.0,
            'ml_learning_rate': 0.0,
            'regression_prediction': 0.0,
            'breakout_probability_ml': 0.0,
            'optimal_deployment_score': 0.0,
            'performance_variance': 0.0,
            'prediction_accuracy': PredictionAccuracy.MODERATE,
            'development_tracking_points': 0,
            'ml_model_updates': 0,
            'prediction_error_rate': 0.0
        } for p in home_team.roster + away_team.roster}
        
        # Initialize fatigue for all players
        for player in home_team.roster + away_team.roster:
            self.player_fatigue[player.id] = 100  # Start at 100% energy
            
        # Initialize Stage 5 goaltender tracking
        for player in home_team.roster + away_team.roster:
            if player.primary_position == PlayerPosition.GOALIE:
                self.goaltender_fatigue[player.id] = 100  # Start at 100% energy
                self.goaltender_positioning[player.id] = GoaltenderPosition.IN_NET
                self.save_quality_tracking[player.id] = {
                    'total_expected_goals_against': 0.0,
                    'actual_goals_against': 0,
                    'saves_by_type': {},
                    'save_difficulty_distribution': {'easy': 0, 'medium': 0, 'hard': 0}
                }
        
        # Team-level advanced stats (Stages 1, 2 & 3)
        self.team_stats = {
            self.home_team.team_name: {
                # Stage 1 stats
                'shots_on_goal': 0,
                'shot_attempts': 0,
                'blocked_shots': 0,
                'shots_blocked': 0,
                'high_danger_chances': 0,
                'corsi_for': 0,
                'corsi_against': 0,
                # Stage 2 stats
                'zone_time_offensive': 0,
                'zone_time_defensive': 0,
                'zone_entries': 0,
                'zone_exits': 0,
                'controlled_entries': 0,
                'dump_ins': 0,
                'possession_time': 0,
                'puck_battles_won': 0,
                'puck_battles_lost': 0,
                # Stage 3 stats
                'faceoffs_won': 0,
                'faceoffs_lost': 0,
                'faceoff_win_percentage': 0,
                'power_play_opportunities': 0,
                'power_play_goals': 0,
                'power_play_percentage': 0,
                'penalty_kill_opportunities': 0,
                'penalty_kill_goals_against': 0,
                'penalty_kill_percentage': 0,
                'short_handed_goals': 0,
                'power_play_shots': 0,
                'penalty_kill_shots_against': 0,
                # Stage 4 stats
                'hits': 0,
                'hits_against': 0,
                'takeaways': 0,
                'giveaways': 0,
                'turnovers_forced': 0,
                'turnovers_committed': 0,
                'blocked_shots_by_team': 0,
                'shots_blocked_against_team': 0,
                'defensive_zone_time': 0,
                'checking_effectiveness': 0,
                'physical_penalties': 0,
                # Stage 5 stats
                'goals_against': 0,
                'saves': 0,
                'shots_against': 0,
                'team_save_percentage': 0.0,
                'goals_saved_above_expected': 0.0,
                'high_danger_saves': 0,
                'medium_danger_saves': 0,
                'low_danger_saves': 0,
                'shutouts': 0,
                'quality_starts': 0,
                'goaltending_rating': 0.0,
                # Stage 6 stats
                'line_chemistry_average': 0.0,
                'chemistry_bonuses_applied': 0,
                'coaching_adjustments': 0,
                'role_effectiveness': 0.0,
                'tactical_success_rate': 0.0,
                'line_matching_advantage': 0,
                'chemistry_goals': 0,
                'chemistry_assists': 0,
                
                # Stage 7 stats
                'momentum_shifts': 0,
                'momentum_advantage_time': 0.0,
                'pressure_generated': 0.0,
                'pressure_sustained': 0.0,
                'micro_event_wins': 0,
                'micro_event_losses': 0,
                'transition_efficiency': 0.0,
                'situational_success_rate': 0.0,
                'flow_control': 0.0,
                'clutch_moments': 0,
                'clutch_success': 0,
                'leadership_interventions': 0,
                'communication_quality': 0.0,
                
                # Stage 8 stats - Advanced Analytics
                'expected_goals_for': 0.0,
                'expected_goals_against': 0.0,
                'goals_above_expected': 0.0,
                'predicted_win_probability': 0.5,
                'team_war': 0.0,  # Wins Above Replacement
                'clutch_rating': 0.0,
                'situational_performance': {},  # Performance by situation
                'lineup_efficiency': {},  # Line combination analytics
                'game_script_adherence': 0.0,  # How close to predicted game flow
                'momentum_prediction_accuracy': 0.0,
                'analytics_adjustments_made': 0,
                'predictive_model_accuracy': 0.0,
                'real_time_optimizations': 0,
                
                # Stage 9 stats - Situational Awareness & AI
                'ai_decisions_made': 0,
                'situational_awareness_accuracy': 0.0,
                'adaptive_strategy_changes': 0,
                'context_recognition_success': 0.0,
                'intelligent_timeout_usage': 0,
                'tactical_adaptation_rate': 0.0,
                'decision_confidence_average': 0.0,
                'ai_learning_improvements': 0,
                'opponent_pattern_recognition': 0.0,
                'game_state_management_score': 0.0,
                'coaching_intervention_success': 0.0,
                'momentum_response_effectiveness': 0.0,
                'situational_context_switches': 0,
                
                # Stage 10 stats - Machine Learning & Performance Prediction
                'ml_predictions_made': 0,
                'prediction_accuracy_rate': 0.0,
                'development_projections': 0,
                'performance_regression_accuracy': 0.0,
                'injury_predictions': 0,
                'game_outcome_predictions': 0,
                'lineup_optimizations': 0,
                'ml_model_confidence': 0.0,
                'prediction_variance': 0.0,
                'development_tracking_score': 0.0,
                'performance_prediction_error': 0.0,
                'optimization_improvements': 0.0,
                'ml_learning_rate': 0.0
            },
            self.away_team.team_name: {
                # Stage 1 stats
                'shots_on_goal': 0,
                'shot_attempts': 0,
                'blocked_shots': 0,
                'shots_blocked': 0,
                'high_danger_chances': 0,
                'corsi_for': 0,
                'corsi_against': 0,
                # Stage 2 stats
                'zone_time_offensive': 0,
                'zone_time_defensive': 0,
                'zone_entries': 0,
                'zone_exits': 0,
                'controlled_entries': 0,
                'dump_ins': 0,
                'possession_time': 0,
                'puck_battles_won': 0,
                'puck_battles_lost': 0,
                # Stage 3 stats
                'faceoffs_won': 0,
                'faceoffs_lost': 0,
                'faceoff_win_percentage': 0,
                'power_play_opportunities': 0,
                'power_play_goals': 0,
                'power_play_percentage': 0,
                'penalty_kill_opportunities': 0,
                'penalty_kill_goals_against': 0,
                'penalty_kill_percentage': 0,
                'short_handed_goals': 0,
                'power_play_shots': 0,
                'penalty_kill_shots_against': 0,
                # Stage 4 stats
                'hits': 0,
                'hits_against': 0,
                'takeaways': 0,
                'giveaways': 0,
                'turnovers_forced': 0,
                'turnovers_committed': 0,
                'blocked_shots_by_team': 0,
                'shots_blocked_against_team': 0,
                'defensive_zone_time': 0,
                'checking_effectiveness': 0,
                'physical_penalties': 0,
                # Stage 5 stats
                'goals_against': 0,
                'saves': 0,
                'shots_against': 0,
                'team_save_percentage': 0.0,
                'goals_saved_above_expected': 0.0,
                'high_danger_saves': 0,
                'medium_danger_saves': 0,
                'low_danger_saves': 0,
                'shutouts': 0,
                'quality_starts': 0,
                'goaltending_rating': 0.0,
                # Stage 6 stats
                'line_chemistry_average': 0.0,
                'chemistry_bonuses_applied': 0,
                'coaching_adjustments': 0,
                'role_effectiveness': 0.0,
                'tactical_success_rate': 0.0,
                'line_matching_advantage': 0,
                'chemistry_goals': 0,
                'chemistry_assists': 0,
                
                # Stage 7 stats
                'momentum_shifts': 0,
                'momentum_advantage_time': 0.0,
                'pressure_generated': 0.0,
                'pressure_sustained': 0.0,
                'micro_event_wins': 0,
                'micro_event_losses': 0,
                'transition_efficiency': 0.0,
                'situational_success_rate': 0.0,
                'flow_control': 0.0,
                'clutch_moments': 0,
                'clutch_success': 0,
                'leadership_interventions': 0,
                'communication_quality': 0.0,
                
                # Stage 8 stats - Advanced Analytics
                'expected_goals_for': 0.0,
                'expected_goals_against': 0.0,
                'goals_above_expected': 0.0,
                'predicted_win_probability': 0.5,
                'team_war': 0.0,  # Wins Above Replacement
                'clutch_rating': 0.0,
                'situational_performance': {},  # Performance by situation
                'lineup_efficiency': {},  # Line combination analytics
                'game_script_adherence': 0.0,  # How close to predicted game flow
                'momentum_prediction_accuracy': 0.0,
                'analytics_adjustments_made': 0,
                'predictive_model_accuracy': 0.0,
                'real_time_optimizations': 0,
                
                # Stage 9 stats - Situational Awareness & AI
                'ai_decisions_made': 0,
                'situational_awareness_accuracy': 0.0,
                'adaptive_strategy_changes': 0,
                'context_recognition_success': 0.0,
                'intelligent_timeout_usage': 0,
                'tactical_adaptation_rate': 0.0,
                'decision_confidence_average': 0.0,
                'ai_learning_improvements': 0,
                'opponent_pattern_recognition': 0.0,
                'game_state_management_score': 0.0,
                'coaching_intervention_success': 0.0,
                'momentum_response_effectiveness': 0.0,
                'situational_context_switches': 0,
                
                # Stage 10 stats - Machine Learning & Performance Prediction
                'ml_predictions_made': 0,
                'prediction_accuracy_rate': 0.0,
                'development_projections': 0,
                'performance_regression_accuracy': 0.0,
                'injury_predictions': 0,
                'game_outcome_predictions': 0,
                'lineup_optimizations': 0,
                'ml_model_confidence': 0.0,
                'prediction_variance': 0.0,
                'development_tracking_score': 0.0,
                'performance_prediction_error': 0.0,
                'optimization_improvements': 0.0,
                'ml_learning_rate': 0.0
            }
        }
        
        # Initialize Stage 6 systems
        self._initialize_stage6_systems()
        
        # Initialize Stage 7 systems
        self._initialize_stage7_systems()
        
        # Initialize Stage 8 systems
        self._initialize_stage8_systems()
        
        # Initialize Stage 9 systems
        self._initialize_stage9_systems()
        
        # Initialize Stage 10 systems
        self._initialize_stage10_systems()

    def _initialize_stage6_systems(self):
        """
        Stage 6: Initialize chemistry, coaching, and line combination systems.
        """
        # Calculate initial line chemistry for all possible line combinations
        self._calculate_initial_chemistry()
        
        # Set default coaching style and tactical system
        self._set_default_coaching_styles()
        
        # Initialize role assignments for all players
        self._assign_player_roles()
        
        # Set up line tracking systems
        self._initialize_line_tracking()

    def _calculate_initial_chemistry(self):
        """
        Stage 6: Calculate starting chemistry between all potential linemates.
        """
        for team in [self.home_team, self.away_team]:
            forwards = [p for p in team.roster if p.primary_position in 
                       [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]]
            defensemen = [p for p in team.roster if p.primary_position in 
                         [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]]
            
            # Calculate forward line chemistry (groups of 3)
            for i in range(0, len(forwards), 3):
                if i + 2 < len(forwards):
                    line_players = forwards[i:i+3]
                    line_id = f"{team.team_name}_forward_line_{i//3 + 1}"
                    chemistry = self._calculate_line_chemistry(line_players)
                    self.line_chemistry[line_id] = chemistry
                    
                    # Track individual player chemistry with linemates
                    for player in line_players:
                        for linemate in line_players:
                            if player != linemate:
                                if player.id not in self.game_stats:
                                    continue
                                if 'linemate_synergy' not in self.game_stats[player.id]:
                                    self.game_stats[player.id]['linemate_synergy'] = {}
                                self.game_stats[player.id]['linemate_synergy'][linemate.id] = chemistry
            
            # Calculate defense pair chemistry (groups of 2)
            for i in range(0, len(defensemen), 2):
                if i + 1 < len(defensemen):
                    pair_players = defensemen[i:i+2]
                    pair_id = f"{team.team_name}_defense_pair_{i//2 + 1}"
                    chemistry = self._calculate_line_chemistry(pair_players)
                    self.line_chemistry[pair_id] = chemistry
                    
                    # Track individual player chemistry
                    for player in pair_players:
                        for linemate in pair_players:
                            if player != linemate:
                                if player.id not in self.game_stats:
                                    continue
                                if 'linemate_synergy' not in self.game_stats[player.id]:
                                    self.game_stats[player.id]['linemate_synergy'] = {}
                                self.game_stats[player.id]['linemate_synergy'][linemate.id] = chemistry

    def _calculate_line_chemistry(self, players):
        """
        Stage 6: Calculate chemistry rating between a group of players (0-100).
        """
        if len(players) < 2:
            return 50.0  # Neutral chemistry for single player
        
        total_chemistry = 0
        comparisons = 0
        
        for i, player1 in enumerate(players):
            for j, player2 in enumerate(players):
                if i != j:
                    # Base chemistry from compatible attributes
                    chemistry = 50.0  # Start neutral
                    
                    # Personality compatibility
                    leadership_diff = abs(player1.leadership - player2.leadership)
                    teamwork_compatibility = (player1.teamwork + player2.teamwork) / 2
                    chemistry += (teamwork_compatibility - 10) * 2  # Teamwork bonus
                    chemistry -= leadership_diff * 0.5  # Leadership clash penalty
                    
                    # Skill compatibility (players of similar skill work better together)
                    skill1 = (player1.skating + player1.passing + player1.hockey_iq) / 3
                    skill2 = (player2.skating + player2.passing + player2.hockey_iq) / 3
                    skill_gap = abs(skill1 - skill2)
                    chemistry -= skill_gap * 0.3  # Skill gap penalty
                    
                    # Playing style compatibility
                    style1 = (player1.flair + player1.offensive_awareness) / 2
                    style2 = (player2.flair + player2.offensive_awareness) / 2
                    style_compatibility = 100 - abs(style1 - style2)
                    chemistry += style_compatibility * 0.2
                    
                    # Age compatibility (similar ages work better)
                    age_diff = abs(player1.age - player2.age)
                    if age_diff <= 2:
                        chemistry += 5  # Close age bonus
                    elif age_diff >= 8:
                        chemistry -= 3  # Large age gap penalty
                    
                    # Position synergy bonuses
                    chemistry += self._get_position_synergy_bonus(player1, player2)
                    
                    # Archetype complementarity: playmakers feed snipers,
                    # shutdown pairings balance offensive defensemen, etc.
                    try:
                        chemistry += complementarity(
                            get_archetype(player1), get_archetype(player2))
                    except Exception:
                        pass

                    total_chemistry += max(0, min(100, chemistry))
                    comparisons += 1
        
        return total_chemistry / comparisons if comparisons > 0 else 50.0

    def _get_position_synergy_bonus(self, player1, player2):
        """
        Stage 6: Calculate position-specific synergy bonuses.
        """
        pos1, pos2 = player1.primary_position, player2.primary_position
        
        # Center-Winger synergy
        if ((pos1 == PlayerPosition.CENTER and pos2 in [PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]) or
            (pos2 == PlayerPosition.CENTER and pos1 in [PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING])):
            
            center = player1 if pos1 == PlayerPosition.CENTER else player2
            winger = player2 if pos1 == PlayerPosition.CENTER else player1
            
            # Playmaking center with skilled winger
            if center.passing >= 15 and winger.offensive_awareness >= 15:
                return 8
            elif center.passing >= 12 and winger.offensive_awareness >= 12:
                return 4
            return 2
        
        # Defense pair synergy
        if (pos1 in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE] and
            pos2 in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]):
            
            # Offensive-Defensive pairing
            off_defender = player1 if player1.offensive_awareness > player1.defensive_awareness else player2
            def_defender = player2 if player1.offensive_awareness > player1.defensive_awareness else player1
            
            if (off_defender.offensive_awareness >= 14 and def_defender.defensive_awareness >= 14):
                return 6
            return 2
        
        return 0

    def _set_default_coaching_styles(self):
        """
        Stage 6: Set default coaching styles and tactical systems for teams.
        """
        # Default coaching adjustments (can be modified by actual coaching stats)
        self.coaching_adjustments = {
            SpecialSituation.EVEN_STRENGTH: {'home': 1.0, 'away': 1.0},
            SpecialSituation.POWER_PLAY: {'home': 1.1, 'away': 1.1},
            SpecialSituation.PENALTY_KILL: {'home': 1.05, 'away': 1.05},
            SpecialSituation.FOUR_ON_FOUR: {'home': 1.08, 'away': 1.08},
            SpecialSituation.THREE_ON_THREE: {'home': 1.15, 'away': 1.15}
        }
        
        # Set default tactical system (could be based on team attributes)
        self.tactical_system = TacticalSystem.CYCLE_GAME

    def _assign_player_roles(self):
        """
        Stage 6: Assign optimal roles to players based on their attributes.
        """
        for team in [self.home_team, self.away_team]:
            for player in team.roster:
                if player.id not in self.game_stats:
                    continue
                    
                role = self._determine_player_role(player)
                effectiveness = self._calculate_role_effectiveness(player, role)
                
                self.role_performance[player.id] = {
                    'role': role,
                    'effectiveness': effectiveness,
                    'role_bonus': effectiveness / 100.0
                }
                
                self.game_stats[player.id]['role_effectiveness'] = effectiveness

    def _determine_player_role(self, player):
        """
        Determine the optimal role for a player from their archetype.
        Archetypes are classified from true attributes (player_archetypes),
        replacing the old hard-coded thresholds.
        """
        try:
            arch = get_archetype(player)
            role_name = ARCHETYPE_TO_ROLE_NAME.get(arch)
            if role_name and hasattr(LineRole, role_name):
                return getattr(LineRole, role_name)
        except Exception:
            pass
        # Fallbacks by position group
        pos = player.primary_position
        if pos in [PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
                   PlayerPosition.RIGHT_WING]:
            return LineRole.GRINDER
        elif pos in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE,
                     PlayerPosition.DEFENSE]:
            return LineRole.TWO_WAY_DEFENDER
        return LineRole.GRINDER

    def _calculate_role_effectiveness(self, player, role):
        """
        Stage 6: Calculate how effectively a player can perform their assigned role (0-100).
        """
        base_effectiveness = 50.0
        
        # Effectiveness comes from the player's archetype fit: average the
        # archetype's key attributes (50-point scale) into a 0-100 rating.
        # Map: 25 -> 0, 37.5 -> 50, 50 -> 100.
        try:
            arch = get_archetype(player)
            fit = ARCHETYPE_FIT.get(arch)
            if fit and fit.get("attributes"):
                vals = [_arch_attr(player, k)
                        for k in fit["attributes"]]
                vals = [v for v in vals if v > 0]
                if vals:
                    avg = sum(vals) / len(vals)
                    base_effectiveness = max(0.0, min(100.0, (avg - 25.0) * 4.0))
        except Exception:
            pass

        # Add personality modifiers (50-point scale aware)
        if role == LineRole.ENFORCER:
            base_effectiveness += (player.aggressiveness - 35) * 0.5
        elif role == LineRole.DEFENSIVE_FORWARD:
            base_effectiveness += (player.work_rate - 35) * 0.3
        elif role == LineRole.PLAYMAKER:
            base_effectiveness += (player.hockey_iq - 35) * 0.3

        return max(0, min(100, base_effectiveness))

    def _initialize_line_tracking(self):
        """
        Stage 6: Initialize systems for tracking line performance and fatigue.
        """
        # Initialize line fatigue tracking
        for line_id in self.line_chemistry.keys():
            self.line_fatigue[line_id] = 100.0  # Start at 100% energy
        
        # Initialize chemistry evolution tracking
        self.chemistry_evolution = {
            'positive_events': {},  # Events that improve chemistry
            'negative_events': {},  # Events that hurt chemistry
            'games_together': {}    # Track how long players have been together
        }

    def _initialize_stage7_systems(self):
        """
        Stage 7: Initialize micro-event tracking, momentum, and game flow systems.
        """
        # Initialize momentum and flow
        self.momentum = GameMomentum.NEUTRAL
        self.game_flow = GameFlow.NORMAL
        self.pressure_level = PressureLevel.MODERATE
        self.situational_context = SituationalContext.GAME_OPENING
        
        # Initialize micro-event tracking
        self.micro_events = []
        self.momentum_history = []
        
        # Initialize pressure zones (by ice location)
        self.pressure_zones = {
            'offensive_zone': 0.0,
            'neutral_zone': 0.0,
            'defensive_zone': 0.0
        }
        
        # Initialize transition tracking
        self.transition_sequences = []
        
        # Initialize contextual adjustments
        self.contextual_adjustments = {
            'late_period': 1.0,
            'overtime': 1.0,
            'empty_net': 1.0,
            'final_minute': 1.0,
            'momentum_building': 1.0
        }
        
        # Initialize flow multipliers for different actions
        self.flow_multipliers = {
            'shot_frequency': 1.0,
            'passing_accuracy': 1.0,
            'checking_intensity': 1.0,
            'line_changes': 1.0,
            'mistake_likelihood': 1.0
        }

    def _initialize_stage8_systems(self):
        """
        Stage 8: Initialize advanced analytics integration, predictive modeling, and real-time analysis.
        """
        # Initialize analytics engine
        self.analytics_engine = {
            'expected_goals': 0.0,
            'win_probability': 0.5,
            'momentum_tracker': 0.0,
            'clutch_factor': 1.0
        }
        
        # Initialize prediction models
        self.prediction_models = {
            AnalyticsModel.EXPECTED_GOALS: {'accuracy': 0.0, 'predictions': []},
            AnalyticsModel.WIN_PROBABILITY: {'current': 0.5, 'history': []},
            AnalyticsModel.PLAYER_IMPACT: {'calculations': {}, 'trends': {}},
            AnalyticsModel.LINEUP_OPTIMIZATION: {'suggestions': {}, 'effectiveness': {}},
            AnalyticsModel.GAME_SCRIPT: {'predicted_flow': [], 'actual_flow': []},
            AnalyticsModel.MOMENTUM_TRACKING: {'shifts': [], 'predictions': []},
            AnalyticsModel.CLUTCH_FACTOR: {'situations': [], 'performance': {}}
        }
        
        # Initialize performance trends for all players
        for player in self.home_team.roster + self.away_team.roster:
            self.performance_trends[player.id] = {
                'recent_games': [],
                'trend_direction': TrendDirection.STABLE,
                'hot_streak': False,
                'cold_streak': False,
                'breakout_probability': 0.0,
                'regression_risk': 0.0
            }
        
        # Initialize expected goals model
        self.expected_goals_model = {
            'shot_quality_weights': {
                'distance': 0.3,
                'angle': 0.2,
                'shot_type': 0.25,
                'traffic': 0.15,
                'rush': 0.1
            },
            'historical_conversion_rates': {},
            'goalie_adjustments': {},
            'situational_modifiers': {}
        }
        
        # Initialize WAR tracking
        self.player_war_tracking = {}
        for player in self.home_team.roster + self.away_team.roster:
            self.player_war_tracking[player.id] = {
                'offense_war': 0.0,
                'defense_war': 0.0,
                'special_teams_war': 0.0,
                'total_war': 0.0,
                'replacement_level': self._calculate_replacement_level(player)
            }
        
        # Initialize clutch situation tracking
        self.clutch_situations = []
        
        # Initialize game script analysis
        self.game_script_analysis = {
            'predicted_events': [],
            'actual_events': [],
            'adherence_score': 1.0,
            'major_deviations': []
        }
        
        # Initialize lineup analytics
        self.lineup_analytics = {}
        
        # Initialize momentum predictors
        self.momentum_predictors = {
            'recent_events_weight': 0.4,
            'score_differential_weight': 0.3,
            'time_remaining_weight': 0.2,
            'special_situations_weight': 0.1
        }
        
        # Initialize situational analytics
        self.situational_analytics = {
            'even_strength': {'efficiency': 1.0, 'sample_size': 0},
            'power_play': {'efficiency': 1.0, 'sample_size': 0},
            'penalty_kill': {'efficiency': 1.0, 'sample_size': 0},
            'late_game': {'efficiency': 1.0, 'sample_size': 0},
            'overtime': {'efficiency': 1.0, 'sample_size': 0}
        }
        
        # Initialize real-time adjustments
        self.real_time_adjustments = {
            'line_changes': [],
            'tactical_shifts': [],
            'special_teams_adjustments': [],
            'analytics_driven_decisions': []
        }
        
        # Initialize Stage 9 systems
        self._initialize_stage9_systems()

    def _initialize_stage9_systems(self):
        """
        Stage 9: Initialize situational awareness and AI decision-making systems.
        """
        # AI Decision Engine
        self.ai_decision_engine = {
            'decision_history': [],
            'confidence_tracker': {},
            'learning_patterns': {},
            'situational_memory': [],
            'adaptation_rate': 0.1,
            'decision_success_rate': 0.0
        }
        
        # Situational Awareness System
        self.situational_awareness = {
            'current_context': SituationalContext.GAME_OPENING,
            'context_history': [],
            'context_confidence': AIConfidenceLevel.MODERATE,
            'situation_weights': {},
            'pattern_recognition': {},
            'contextual_modifiers': {}
        }
        
        # Adaptive Strategy Engine
        self.adaptive_strategy = {
            'current_strategy': AdaptiveStrategy.BALANCED_ATTACK,
            'strategy_history': [],
            'strategy_effectiveness': {},
            'adaptation_triggers': {},
            'real_time_adjustments': [],
            'opponent_counters': {}
        }
        
        # AI Learning System
        self.ai_learning = {
            'learning_mode': AILearningMode.REAL_TIME_ADJUSTMENT,
            'pattern_database': {},
            'success_patterns': {},
            'failure_patterns': {},
            'adaptation_insights': [],
            'opponent_tendencies': {}
        }
        
        # Intelligent Coaching System
        self.intelligent_coaching = {
            'timeout_strategy': {},
            'line_optimization': {},
            'tactical_responses': {},
            'momentum_management': {},
            'game_state_responses': {},
            'player_management': {}
        }
        
        # Context-Aware Decision Making
        self.context_decisions = {
            'decision_queue': [],
            'priority_decisions': [],
            'contextual_weights': {},
            'decision_timing': {},
            'outcome_tracking': {},
            'confidence_adjustments': {}
        }

    def _initialize_stage10_systems(self):
        """
        Stage 10: Initialize machine learning and performance prediction systems.
        """
        # ML Model Registry
        self.ml_models = {
            'player_development': {
                'model_type': MLModelType.PLAYER_DEVELOPMENT,
                'training_data': [],
                'accuracy': PredictionAccuracy.MODERATE,
                'last_update': 0,
                'prediction_count': 0,
                'confidence_threshold': 0.7
            },
            'performance_regression': {
                'model_type': MLModelType.PERFORMANCE_REGRESSION,
                'training_data': [],
                'accuracy': PredictionAccuracy.MODERATE,
                'last_update': 0,
                'prediction_count': 0,
                'confidence_threshold': 0.75
            },
            'injury_prediction': {
                'model_type': MLModelType.INJURY_PREDICTION,
                'training_data': [],
                'accuracy': PredictionAccuracy.MODERATE,
                'last_update': 0,
                'prediction_count': 0,
                'confidence_threshold': 0.8
            },
            'game_outcome': {
                'model_type': MLModelType.GAME_OUTCOME,
                'training_data': [],
                'accuracy': PredictionAccuracy.MODERATE,
                'last_update': 0,
                'prediction_count': 0,
                'confidence_threshold': 0.65
            },
            'lineup_optimization': {
                'model_type': MLModelType.LINEUP_OPTIMIZATION,
                'training_data': [],
                'accuracy': PredictionAccuracy.MODERATE,
                'last_update': 0,
                'prediction_count': 0,
                'confidence_threshold': 0.6
            },
            'trade_value': {
                'model_type': MLModelType.TRADE_VALUE,
                'training_data': [],
                'accuracy': PredictionAccuracy.MODERATE,
                'last_update': 0,
                'prediction_count': 0,
                'confidence_threshold': 0.7
            },
            'season_projection': {
                'model_type': MLModelType.SEASON_PROJECTION,
                'training_data': [],
                'accuracy': PredictionAccuracy.MODERATE,
                'last_update': 0,
                'prediction_count': 0,
                'confidence_threshold': 0.65
            }
        }
        
        # Performance Prediction Engine
        self.performance_predictor = {
            'prediction_history': [],
            'accuracy_tracking': {},
            'model_confidence': {},
            'prediction_variance': {},
            'learning_rate': 0.05,
            'adaptation_speed': OptimizationTarget.BALANCE_OFFENSE_DEFENSE,
            'validation_results': {}
        }
        
        # Player Development Tracker
        self.development_tracker = {
            'development_patterns': {},
            'trajectory_models': {},
            'breakout_indicators': {},
            'regression_markers': {},
            'career_phase_tracking': {},
            'potential_realizations': {}
        }
        
        # ML Optimization Engine
        self.ml_optimizer = {
            'optimization_targets': [OptimizationTarget.MAXIMIZE_GOALS, OptimizationTarget.MINIMIZE_GOALS_AGAINST],
            'optimization_history': [],
            'success_metrics': {},
            'learning_adjustments': {},
            'model_improvements': {},
            'predictive_insights': {}
        }
        
        # Advanced Analytics ML
        self.advanced_ml_analytics = {
            'performance_metrics': [PerformanceMetric.EXPECTED_PERFORMANCE, PerformanceMetric.REGRESSION_COEFFICIENT],
            'metric_predictions': {},
            'trend_analysis': {},
            'anomaly_detection': {},
            'pattern_recognition': {},
            'predictive_modeling': {}
        }

    def _calculate_replacement_level(self, player):
        """
        Stage 8: Calculate replacement level baseline for WAR calculations.
        """
        # Basic replacement level based on position and league average
        position_baselines = {
            PlayerPosition.CENTER: 0.45,
            PlayerPosition.LEFT_WING: 0.40,
            PlayerPosition.RIGHT_WING: 0.40,
            PlayerPosition.DEFENSE: 0.35,
            PlayerPosition.GOALIE: 0.50
        }
        
        base_replacement = position_baselines.get(player.primary_position, 0.40)
        
        # Adjust for player's overall rating relative to league average (assumed 75)
        league_average = 75
        rating_adjustment = (player.overall_rating() - league_average) / 100
        
        return max(0.1, base_replacement + rating_adjustment)

    # =====================================================
    # STAGE 10: MACHINE LEARNING & PERFORMANCE PREDICTION METHODS
    # =====================================================

    def _train_prediction_models(self):
        """Stage 10: Train ML models using accumulated game data."""
        for model_name, model_data in self.ml_models.items():
            if len(model_data['training_data']) >= 10:  # Minimum training data
                # Simulate model training and accuracy improvement
                training_effectiveness = min(len(model_data['training_data']) / 100, 0.95)
                
                # Update model accuracy based on training data
                current_accuracy = model_data['accuracy']
                if current_accuracy == PredictionAccuracy.LOW:
                    if training_effectiveness > 0.3:
                        model_data['accuracy'] = PredictionAccuracy.MODERATE
                elif current_accuracy == PredictionAccuracy.MODERATE:
                    if training_effectiveness > 0.6:
                        model_data['accuracy'] = PredictionAccuracy.HIGH
                elif current_accuracy == PredictionAccuracy.HIGH:
                    if training_effectiveness > 0.8:
                        model_data['accuracy'] = PredictionAccuracy.VERY_HIGH
                
                model_data['last_update'] = self.clock
                
                # Update team ML stats
                for team_name in self.team_stats:
                    self.team_stats[team_name]['ml_learning_rate'] += 0.1

    def _predict_player_development(self, player):
        """Stage 10: Predict player's development trajectory using ML."""
        player_id = player.id
        current_performance = self.game_stats[player_id]
        
        # Factor in various performance metrics
        scoring_trend = current_performance['g'] + current_performance['a']
        advanced_metrics = current_performance['expected_goals'] + current_performance['war']
        consistency = 1.0 - current_performance['performance_variance']
        
        # Calculate development prediction
        development_score = (scoring_trend * 0.3 + advanced_metrics * 0.4 + consistency * 0.3)
        
        # Determine development phase
        if development_score > 2.0:
            phase = DevelopmentPhase.PRIME_PEAK
        elif development_score > 1.5:
            phase = DevelopmentPhase.PRIME_EARLY
        elif development_score > 1.0:
            phase = DevelopmentPhase.DEVELOPING
        elif development_score > 0.5:
            phase = DevelopmentPhase.PROSPECT
        elif development_score > 0.0:
            phase = DevelopmentPhase.DECLINING
        else:
            phase = DevelopmentPhase.VETERAN
        
        # Update player stats
        self.game_stats[player_id]['development_prediction'] = phase
        self.game_stats[player_id]['development_tracking_points'] += 1
        
        # Track prediction for model training
        model_data = self.ml_models['player_development']
        model_data['training_data'].append({
            'player_id': player_id,
            'prediction': phase,
            'timestamp': self.clock,
            'input_data': development_score
        })
        model_data['prediction_count'] += 1
        
        return phase

    def _calculate_performance_projection(self, player):
        """Stage 10: Calculate expected performance trajectory."""
        player_id = player.id
        current_stats = self.game_stats[player_id]
        
        # Analyze recent performance trends
        recent_performance = (
            current_stats['expected_goals'] + 
            current_stats['goals_above_expected'] + 
            current_stats['war'] * 0.5
        )
        
        # Factor in age and experience (simulated)
        age_factor = 1.0  # Would be based on actual player age
        experience_factor = min(current_stats['ai_learning_contribution'] / 10, 1.0)
        
        # Calculate projection confidence
        prediction_variance = abs(recent_performance - current_stats['predictive_performance'])
        confidence = max(0.1, 1.0 - (prediction_variance / 5.0))
        
        # Update player projections
        trajectory = recent_performance * age_factor * experience_factor
        self.game_stats[player_id]['performance_trajectory'] = trajectory
        self.game_stats[player_id]['career_projection_confidence'] = confidence
        
        # Update team predictions
        team_name = self._get_player_team(player).team_name
        self.team_stats[team_name]['development_projections'] += 1
        
        return trajectory, confidence

    def _assess_injury_risk(self, player):
        """Stage 10: Use ML to assess injury probability."""
        player_id = player.id
        current_stats = self.game_stats[player_id]
        
        # Risk factors
        physical_load = (
            current_stats['hits'] + 
            current_stats['hits_taken'] + 
            current_stats['physical_penalties']
        )
        fatigue_factor = (100 - self.player_fatigue.get(player_id, 100)) / 100
        usage_intensity = current_stats['possession_time'] / max(1, self.clock)
        
        # Calculate risk score
        base_risk = 0.05  # 5% baseline risk
        physical_risk = physical_load * 0.01
        fatigue_risk = fatigue_factor * 0.15
        usage_risk = usage_intensity * 0.05
        
        total_risk = min(0.95, base_risk + physical_risk + fatigue_risk + usage_risk)
        
        # Update player stats
        self.game_stats[player_id]['injury_risk_score'] = total_risk
        
        # Update team injury predictions
        team_name = self._get_player_team(player).team_name
        self.team_stats[team_name]['injury_predictions'] += 1
        
        # Add to ML training data
        model_data = self.ml_models['injury_prediction']
        model_data['training_data'].append({
            'player_id': player_id,
            'risk_score': total_risk,
            'factors': {
                'physical_load': physical_load,
                'fatigue': fatigue_factor,
                'usage': usage_intensity
            },
            'timestamp': self.clock
        })
        
        return total_risk

    def _optimize_lineup_deployment(self, team):
        """Stage 10: ML-driven lineup optimization."""
        optimization_score = 0.0
        
        for player in team.roster:
            player_id = player.id
            current_stats = self.game_stats[player_id]
            
            # Calculate optimal deployment score
            effectiveness = current_stats['role_effectiveness']
            chemistry = current_stats['chemistry_rating'] / 100
            situational_fit = current_stats['situational_impact'].get('current', 0.5)
            
            player_optimization = effectiveness * chemistry * situational_fit
            optimization_score += player_optimization
            
            # Update individual player optimization
            self.game_stats[player_id]['optimal_deployment_score'] = player_optimization
        
        # Update team optimization stats
        self.team_stats[team.team_name]['lineup_optimizations'] += 1
        self.team_stats[team.team_name]['optimization_improvements'] += optimization_score / len(team.roster)
        
        # Track in ML model
        model_data = self.ml_models['lineup_optimization']
        model_data['training_data'].append({
            'team': team.team_name,
            'optimization_score': optimization_score,
            'timestamp': self.clock,
            'roster_size': len(team.roster)
        })
        
        return optimization_score

    def _predict_game_outcome(self):
        """Stage 10: ML prediction of game outcome probabilities."""
        home_factors = self._calculate_team_strength(self.home_team)
        away_factors = self._calculate_team_strength(self.away_team)
        
        # Current game state factors
        score_differential = self.home_score - self.away_score
        time_remaining = self.clock / 1200  # Normalize to 0-1
        momentum_factor = self._calculate_team_momentum(self.home_team) - self._calculate_team_momentum(self.away_team)
        
        # ML prediction calculation
        home_win_probability = 0.5 + (
            (home_factors - away_factors) * 0.3 +
            score_differential * 0.1 +
            momentum_factor * 0.1
        )
        home_win_probability = max(0.05, min(0.95, home_win_probability))
        
        # Update team predictions
        self.team_stats[self.home_team.team_name]['game_outcome_predictions'] += 1
        self.team_stats[self.away_team.team_name]['game_outcome_predictions'] += 1
        
        # Track prediction accuracy
        model_data = self.ml_models['game_outcome']
        model_data['training_data'].append({
            'home_probability': home_win_probability,
            'away_probability': 1 - home_win_probability,
            'game_state': {
                'score_diff': score_differential,
                'time_remaining': time_remaining,
                'momentum': momentum_factor
            },
            'timestamp': self.clock
        })
        
        return home_win_probability

    def _update_ml_learning_rates(self):
        """Stage 10: Dynamically adjust ML learning parameters."""
        for player in self.home_team.roster + self.away_team.roster:
            player_id = player.id
            current_stats = self.game_stats[player_id]
            
            # Calculate learning rate based on performance variance
            variance = current_stats['performance_variance']
            prediction_error = current_stats['prediction_error_rate']
            
            # Adaptive learning rate
            base_rate = 0.05
            variance_adjustment = variance * 0.02
            error_adjustment = prediction_error * 0.03
            
            new_learning_rate = max(0.01, min(0.15, base_rate + variance_adjustment + error_adjustment))
            
            # Update player ML stats
            self.game_stats[player_id]['ml_learning_rate'] = new_learning_rate
            self.game_stats[player_id]['ml_model_updates'] += 1
        
        # Update team-wide learning rates
        for team_name in self.team_stats:
            team_variance = sum(self.game_stats[p.id]['performance_variance'] 
                              for p in self.home_team.roster + self.away_team.roster 
                              if self._get_player_team_name(p) == team_name) / 23
            self.team_stats[team_name]['ml_learning_rate'] = max(0.01, min(0.2, 0.1 + team_variance * 0.05))

    def _get_player_team(self, player):
        """Helper method to get team object for a player."""
        if player in self.home_team.roster:
            return self.home_team
        return self.away_team
    
    def _get_player_team_name(self, player):
        """Helper method to get team name for a player."""
        return self._get_player_team(player).team_name

    def _update_ml_predictions(self):
        """Stage 10: Periodic ML updates during gameplay."""
        # Train models if enough data
        self._train_prediction_models()
        
        # Update predictions for key players (currently on ice)
        active_players = self.home_on_ice + self.away_on_ice
        
        for player in active_players:
            # Update development predictions
            self._predict_player_development(player)
            
            # Calculate performance projections
            self._calculate_performance_projection(player)
            
            # Assess injury risk
            self._assess_injury_risk(player)
        
        # Optimize lineup deployment for both teams
        self._optimize_lineup_deployment(self.home_team)
        self._optimize_lineup_deployment(self.away_team)
        
        # Predict game outcome
        win_probability = self._predict_game_outcome()
        
        # Update learning rates
        self._update_ml_learning_rates()
        
        # Update ML confidence tracking
        for team_name in self.team_stats:
            self.team_stats[team_name]['ml_predictions_made'] += 5  # 5 types of predictions
            
            # Calculate overall prediction accuracy (simulated improvement over time)
            base_accuracy = 0.6
            experience_bonus = min(self.team_stats[team_name]['ml_predictions_made'] / 1000, 0.3)
            self.team_stats[team_name]['prediction_accuracy_rate'] = base_accuracy + experience_bonus

    def _calculate_team_strength(self, team):
        """Stage 10: Calculate overall team strength for ML predictions."""
        total_strength = 0.0
        player_count = 0
        
        for player in team.roster:
            player_stats = self.game_stats[player.id]
            
            # Combine multiple performance indicators
            offensive_contribution = player_stats['expected_goals'] + player_stats['goals_above_expected']
            defensive_contribution = player_stats['takeaways'] - player_stats['giveaways']
            advanced_metrics = player_stats['war'] + player_stats['par']
            
            player_strength = offensive_contribution + defensive_contribution + advanced_metrics
            total_strength += player_strength
            player_count += 1
        
        return total_strength / max(1, player_count)

    def _calculate_team_momentum(self, team):
        """Stage 10: Calculate team momentum for game prediction."""
        momentum_factors = 0.0
        
        for player in team.roster:
            player_stats = self.game_stats[player.id]
            
            # Recent performance indicators
            momentum_events = player_stats['momentum_events']
            clutch_performance = player_stats['clutch_performance']
            flow_adaptation = player_stats['flow_adaptation']
            
            player_momentum = momentum_events + clutch_performance + flow_adaptation
            momentum_factors += player_momentum
        
        # Normalize by roster size
        return momentum_factors / len(team.roster)

    def run(self):
        """Runs the entire game simulation from period 1 through OT/shootout if necessary."""
        self._ppos_ensure()
        self._log_event("Game Start!", "PERIOD_START")
        self._emit_pbp("game_start",
                       home_team=self.home_team.team_name,
                       away_team=self.away_team.team_name)

        for p in range(1, 4):
            self.period = p
            self.clock = 1200
            self._period_length = 1200
            self._emit_pbp("period_start", period=p)
            self._simulate_period()
            self._log_event(f"End of Period {self.period}. Score: {self.home_score}-{self.away_score}", "PERIOD_END")
            self._emit_pbp("period_end", period=p)

        if self.home_score == self.away_score:
            self._handle_overtime()

        # Shootout only in regular season; playoffs use continuous sudden-death OT
        if self.home_score == self.away_score and not self.is_playoff:
            self._handle_shootout()
        
        self._check_for_notable_performances()

        winner = self.home_team if self.home_score > self.away_score else self.away_team
        loser = self.away_team if self.home_score > self.away_score else self.home_team
        
        self._emit_pbp("game_end", winner=winner.team_name,
                       home_score=self.home_score, away_score=self.away_score)

        return winner, loser, (self.home_score, self.away_score), self.game_log, self.notable_events
    
    def simulate_game(self):
        """Compatibility wrapper for playoff_system.py.
        
        Calls run() and returns a dict with home_score/away_score,
        matching the interface playoff_system expects.
        """
        winner, loser, scores, game_log, notable_events = self.run()
        home_score, away_score = scores
        return {
            'home_score': home_score,
            'away_score': away_score,
            'winner': winner,
            'loser': loser,
            'game_log': game_log,
            'notable_events': notable_events,
        }

    def _simulate_period(self):
        """
        Stage 2 Enhancement: Simulates a single 20-minute period with zone-based gameplay.
        """
        self._select_starting_lines()
        possession_team = self._resolve_faceoff()
        self.possession_team = possession_team
        self.current_zone = Zone.NEUTRAL_ZONE
        self.zone_time = 0
        self.possession_time = 0

        while self.clock > 0:
            time_elapsed = random.randint(8, 20)  # Slightly faster pace
            self.clock -= time_elapsed
            self.zone_time += time_elapsed
            self.possession_time += time_elapsed

            # Sudden-death OT: stop the period as soon as someone scores
            if getattr(self, '_ot_sudden_death', False) and self._ot_start_score is not None:
                if (self.home_score, self.away_score) != self._ot_start_score:
                    self._log_event(
                        f"Sudden-death goal! Game over: "
                        f"{self.home_score}-{self.away_score}",
                        "GOAL",
                    )
                    break
            
            # Update fatigue and check for line changes
            self._update_fatigue(time_elapsed)
            self._update_penalties(time_elapsed)
            
            # Stage 9: Analyze situational context and make AI decisions
            self._analyze_situational_context()
            
            # Stage 10: Update ML predictions and learning
            if self.clock % 300 == 0:  # Update every 5 minutes of game time
                self._update_ml_predictions()

            # Determine what happens based on current zone and possession
            event_outcome = self._resolve_zone_based_event()
            # Positional safety net: flush any un-emitted movement (throttled)
            try:
                self._emit_skate()
            except Exception:
                pass

            # Force line changes periodically or due to fatigue
            if self._should_change_lines():
                self._select_starting_lines()
                self.line_change_timer = 0

    def _resolve_zone_based_event(self):
        """
        Stage 2: Resolve events based on current zone and possession state.
        """
        if not self.possession_team:
            return self._resolve_loose_puck_battle()
        
        attacking_team = self.possession_team
        defending_team = self.away_team if attacking_team == self.home_team else self.home_team
        
        # Determine event based on current zone
        if self.current_zone == Zone.NEUTRAL_ZONE:
            return self._resolve_neutral_zone_play(attacking_team, defending_team)
        elif self.current_zone == Zone.OFFENSIVE_ZONE:
            return self._resolve_offensive_zone_play(attacking_team, defending_team)
        else:  # DEFENSIVE_ZONE
            return self._resolve_defensive_zone_play(attacking_team, defending_team)

    def _resolve_neutral_zone_play(self, attacking_team, defending_team):
        """
        Stage 4 Enhancement: Handle play in the neutral zone with physical checking and defensive systems.
        """
        attacking_skaters = [p for p in self._get_on_ice(attacking_team) if p.primary_position != PlayerPosition.GOALIE]
        defending_skaters = [p for p in self._get_on_ice(defending_team) if p.primary_position != PlayerPosition.GOALIE]
        
        if not attacking_skaters:
            return self._turnover_possession(defending_team)
        
        puck_carrier = random.choice(attacking_skaters)
        self.possession_player = puck_carrier
        
        # Apply defensive system effects (Stage 4)
        if self.current_defensive_system == DefensiveSystem.NEUTRAL_ZONE_TRAP:
            # Neutral zone trap increases chance of turnover
            if random.random() < 0.25:  # 25% chance
                defender = random.choice(defending_skaters)
                if self._attempt_defensive_play(defender, puck_carrier, DefensiveAction.PASS_INTERCEPTION):
                    return self._resolve_turnover(puck_carrier, defender, TurnoverType.INTERCEPTION)
        
        # Check for physical play in neutral zone (Stage 4)
        # Enforcer deterrence: carriers skate freer with a tough guy on the ice
        # (physical_intensity scales the chance; base 1.0 always allows hits)
        hit_chance = 0.15 * self.physical_intensity
        try:
            mates = [p for p in self._get_on_ice(attacking_team)
                     if p.primary_position != PlayerPosition.GOALIE]
            if any(get_archetype(p) == "Enforcer" for p in mates):
                hit_chance = 0.08 * self.physical_intensity
        except Exception:
            pass
        if random.random() < hit_chance:
            # Archetype tendency: the hitter is usually a power forward,
            # enforcer, grinder or physical defenseman - not a sniper.
            potential_hitter = self._weighted_skater_choice(defending_skaters, "hit")
            hit_result = self._attempt_hit(potential_hitter, puck_carrier, HitType.BODY_CHECK)
            if hit_result == HitResult.TURNOVER_CAUSED:
                return self._resolve_turnover(puck_carrier, potential_hitter, TurnoverType.FORCED_ERROR)
            elif hit_result == HitResult.PENALTY_DRAWN:
                self._resolve_penalty(potential_hitter, defending_team)
        
        # Apply fatigue effects
        fatigue_factor = self.player_fatigue.get(puck_carrier.id, 100) / 100

        # Regroup: move the puck with a pass before the entry attempt
        if random.random() < 0.35:
            self.puck_pos = self._ppos_get(puck_carrier)[:]
            self._shape_positions(attacking_team, self.puck_pos)
            res = self._attempt_pass(puck_carrier, attacking_team, defending_team,
                                     kind="regroup")
            if res is not None and self.possession_team != attacking_team:
                return "Turnover", defending_team
            puck_carrier = getattr(self, "possession_player", None) or puck_carrier

        # Decide on zone entry attempt
        entry_type = self._determine_zone_entry_type(puck_carrier, defending_skaters, fatigue_factor)
        
        if entry_type == ZoneEntryType.CONTROLLED_CARRY:
            return self._attempt_controlled_entry(puck_carrier, attacking_team, defending_team)
        elif entry_type == ZoneEntryType.DUMP_IN:
            return self._attempt_dump_in(puck_carrier, attacking_team, defending_team)
        elif entry_type == ZoneEntryType.PASS_IN:
            return self._attempt_pass_entry(puck_carrier, attacking_team, defending_team)
        else:  # CHIP_IN
            return self._attempt_chip_in(puck_carrier, attacking_team, defending_team)

    def _resolve_offensive_zone_play(self, attacking_team, defending_team):
        """Handle play in the offensive zone - shots, cycles, turnovers."""
        attacking_skaters = [p for p in self._get_on_ice(attacking_team) if p.primary_position != PlayerPosition.GOALIE]
        defending_skaters = [p for p in self._get_on_ice(defending_team) if p.primary_position != PlayerPosition.GOALIE]
        
        if not attacking_skaters:
            return self._zone_clear(defending_team)

        # Grinder wear-down: heavy cycling lines drain defending skaters
        try:
            if any(get_archetype(p) == "Grinder" for p in attacking_skaters):
                for d in defending_skaters:
                    fid = getattr(d, "id", None)
                    if fid in self.player_fatigue:
                        self.player_fatigue[fid] = max(
                            0.0, self.player_fatigue[fid] - 0.6)
        except Exception:
            pass

        # Update zone time stats
        self._update_zone_time_stats(attacking_team, defending_team)
        
        # Random events in offensive zone
        event_roll = random.random()
        
        if event_roll < 0.3:  # 30% chance of shot attempt
            # Archetype tendency: snipers get the puck in shooting spots far
            # more often than playmakers or grinders.
            shooter = self._weighted_skater_choice(attacking_skaters, "shoot")
            self._resolve_scoring_chance(shooter, attacking_team, defending_team)
        elif event_roll < 0.5:  # 20% chance of turnover/zone clear
            return self._attempt_zone_clear(defending_team, attacking_team)
        elif event_roll < 0.7:  # 20% chance of cycling/possession battle
            return self._resolve_offensive_cycle(attacking_team, defending_team)
        else:  # 30% chance of maintain possession
            return self._maintain_offensive_possession(attacking_team)

    def _resolve_defensive_zone_play(self, attacking_team, defending_team):
        """Handle play in the defensive zone - breakouts, clears."""
        # Note: attacking_team has possession but is in their defensive zone
        defending_skaters = [p for p in self._get_on_ice(defending_team) if p.primary_position != PlayerPosition.GOALIE]
        
        # Update zone time stats
        self._update_zone_time_stats(defending_team, attacking_team)  # Flip for defensive zone
        
        # Attempt breakout
        return self._attempt_breakout(attacking_team, defending_team)

    def _determine_zone_entry_type(self, puck_carrier, defenders, fatigue_factor):
        """Determine how the player will attempt to enter the zone."""
        skill_factor = (puck_carrier.skating + puck_carrier.puck_handling + puck_carrier.hockey_iq) / 3
        skill_factor *= fatigue_factor
        
        # Pressure from defenders
        pressure = len(defenders) * 5
        best_defender = max(defenders, key=lambda p: p.checking + p.defensive_awareness) if defenders else None
        if best_defender:
            pressure += (best_defender.checking + best_defender.defensive_awareness) / 2
        
        # Weights based on skill and pressure
        if skill_factor > pressure + 10:
            weights = {
                ZoneEntryType.CONTROLLED_CARRY: 0.6,
                ZoneEntryType.PASS_IN: 0.25,
                ZoneEntryType.CHIP_IN: 0.1,
                ZoneEntryType.DUMP_IN: 0.05
            }
        elif skill_factor > pressure:
            weights = {
                ZoneEntryType.CONTROLLED_CARRY: 0.4,
                ZoneEntryType.PASS_IN: 0.3,
                ZoneEntryType.CHIP_IN: 0.2,
                ZoneEntryType.DUMP_IN: 0.1
            }
        else:
            weights = {
                ZoneEntryType.CONTROLLED_CARRY: 0.2,
                ZoneEntryType.PASS_IN: 0.2,
                ZoneEntryType.CHIP_IN: 0.3,
                ZoneEntryType.DUMP_IN: 0.3
            }

        # Archetype tendency: puck-movers and skilled carriers try to beat
        # defenders one-on-one; grinders and defensive types dump it in.
        try:
            weights[ZoneEntryType.CONTROLLED_CARRY] *= get_tendency(puck_carrier, "carry")
        except Exception:
            pass

        return self._weighted_random_choice(weights)

    def _attempt_controlled_entry(self, puck_carrier, attacking_team, defending_team):
        """Attempt a controlled zone entry."""
        defenders = [p for p in self._get_on_ice(defending_team) if p.primary_position != PlayerPosition.GOALIE]
        
        if not defenders:
            return self._successful_zone_entry(puck_carrier, attacking_team, ZoneEntryType.CONTROLLED_CARRY)
        
        # Best defender attempts to stop entry
        best_defender = max(defenders, key=lambda p: p.checking + p.defensive_awareness + p.anticipation)
        
        # Skill battle
        fatigue_factor = self.player_fatigue.get(puck_carrier.id, 100) / 100
        carrier_skill = (puck_carrier.skating + puck_carrier.deking + puck_carrier.puck_handling) * fatigue_factor
        defender_skill = best_defender.checking + best_defender.defensive_awareness + best_defender.anticipation
        
        carrier_roll = carrier_skill + random.randint(-10, 10)
        defender_roll = defender_skill + random.randint(-10, 10)
        
        if carrier_roll > defender_roll:
            return self._successful_zone_entry(puck_carrier, attacking_team, ZoneEntryType.CONTROLLED_CARRY)
        else:
            self._log_event(f"{best_defender.full_name} forces turnover at the blue line!", "TURNOVER")
            return self._turnover_possession(defending_team)

    def _attempt_dump_in(self, puck_carrier, attacking_team, defending_team):
        """Attempt a dump-in zone entry."""
        self._log_event(f"{puck_carrier.full_name} dumps the puck in deep", "DUMP_IN")
        
        # Update stats
        self.game_stats[puck_carrier.id]['dump_ins'] += 1
        self.team_stats[attacking_team.team_name]['dump_ins'] += 1
        
        # Enter offensive zone
        self.current_zone = Zone.OFFENSIVE_ZONE
        self.zone_time = 0
        
        # Determine who recovers the puck
        attacking_forecheckers = self._get_forecheckers(attacking_team)
        defending_dmen = [p for p in self._get_on_ice(defending_team) 
                         if p.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]]
        
        if attacking_forecheckers and defending_dmen:
            best_attacker = max(attacking_forecheckers, key=lambda p: p.skating + p.anticipation)
            best_defender = max(defending_dmen, key=lambda p: p.defensive_awareness + p.anticipation)
            
            att_roll = best_attacker.skating + best_attacker.anticipation + random.randint(1, 10)
            def_roll = best_defender.defensive_awareness + best_defender.anticipation + random.randint(1, 10)
            
            if att_roll > def_roll:
                self.possession_team = attacking_team
                self.possession_player = best_attacker
                self._log_event(f"{best_attacker.full_name} wins the puck battle", "PUCK_RECOVERY")
                self.game_stats[best_attacker.id]['puck_battles_won'] += 1
            else:
                self.possession_team = defending_team
                self.possession_player = best_defender
                self._log_event(f"{best_defender.full_name} clears the puck", "ZONE_CLEAR")
                self.game_stats[best_defender.id]['puck_battles_won'] += 1
                return self._zone_clear(defending_team)

    def _get_forecheckers(self, team):
        """Get players who would forecheck on a dump-in."""
        forwards = [p for p in self._get_on_ice(team) 
                   if p.primary_position in [PlayerPosition.LEFT_WING, PlayerPosition.CENTER, PlayerPosition.RIGHT_WING]]
        return forwards[:2]  # First 2 forwards forecheck

    def _update_fatigue(self, time_elapsed):
        """
        Stage 2: Update player fatigue based on ice time and intensity.
        """
        for player in self.home_on_ice + self.away_on_ice:
            if player.id in self.player_fatigue:
                # Base fatigue rate (higher for more intense situations)
                fatigue_rate = 0.8  # Base rate per second
                
                # Increase fatigue in offensive/defensive zones
                if self.current_zone != Zone.NEUTRAL_ZONE:
                    fatigue_rate *= 1.3
                
                # Penalty kill increases fatigue significantly
                if self._is_on_penalty_kill(player):
                    fatigue_rate *= 2.0
                
                # Power play slightly increases fatigue
                elif self._is_on_power_play(player):
                    fatigue_rate *= 1.2
                
                # Apply fatigue
                fatigue_loss = fatigue_rate * time_elapsed / 60  # Convert to per-minute rate
                self.player_fatigue[player.id] = max(0, self.player_fatigue[player.id] - fatigue_loss)

    def _should_change_lines(self):
        """Determine if lines should be changed based on fatigue and time."""
        self.line_change_timer += 1
        
        # Force change every 45-60 seconds
        if self.line_change_timer > random.randint(45, 60):
            return True
        
        # Change if key players are too fatigued
        avg_fatigue = sum(self.player_fatigue.get(p.id, 100) for p in self.home_on_ice + self.away_on_ice) / len(self.home_on_ice + self.away_on_ice)
        
        if avg_fatigue < 70:  # 70% fatigue threshold
            return True
        
        # Change during stoppages (faceoffs, goals, etc.)
        return False

    def _successful_zone_entry(self, player, team, entry_type):
        """Handle a successful zone entry."""
        self.current_zone = Zone.OFFENSIVE_ZONE
        self.zone_time = 0
        self.possession_team = team
        self.possession_player = player
        
        # Update stats
        self.game_stats[player.id]['zone_entries'] += 1
        self.team_stats[team.team_name]['zone_entries'] += 1
        
        if entry_type == ZoneEntryType.CONTROLLED_CARRY:
            self.game_stats[player.id]['controlled_zone_entries'] += 1
            self.team_stats[team.team_name]['controlled_entries'] += 1
            self._log_event(f"{player.full_name} carries the puck into the zone", "ZONE_ENTRY")
        
        return "ZONE_ENTRY"

    def _turnover_possession(self, new_team):
        """Handle a change of possession."""
        old_team = self.possession_team
        self.possession_team = new_team
        self.possession_player = None
        self.possession_time = 0
        
        if old_team:
            # Log possession loss for old team players on ice
            for player in self._get_on_ice(old_team):
                if player.id in self.game_stats:
                    self.game_stats[player.id]['possession_losses'] += 1
        
        # Log possession gain for new team
        for player in self._get_on_ice(new_team):
            if player.id in self.game_stats:
                self.game_stats[player.id]['possession_gains'] += 1

        # Positional: transition shape (throttled emit)
        try:
            self._ppos_ensure()
            self._shape_positions(new_team, self.puck_pos)
            self._emit_skate()
        except Exception:
            pass

        return "TURNOVER"

    def _zone_clear(self, clearing_team):
        """Handle a defensive zone clear."""
        self.current_zone = Zone.NEUTRAL_ZONE
        self.zone_time = 0
        self.possession_team = clearing_team
        
        # Find best clearing player
        defenders = [p for p in self._get_on_ice(clearing_team) 
                    if p.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]]
        if defenders:
            clearer = max(defenders, key=lambda p: p.passing + p.defensive_awareness)
            self.possession_player = clearer
            self.game_stats[clearer.id]['zone_exits'] += 1
            self._log_event(f"{clearer.full_name} clears the zone", "ZONE_CLEAR")
            # outlet pass to start the breakout
            other = self.away_team if clearing_team == self.home_team else self.home_team
            self.puck_pos = self._ppos_get(clearer)[:]
            self._shape_positions(clearing_team, self.puck_pos)
            self._attempt_pass(clearer, clearing_team, other, kind="breakout")

        self.team_stats[clearing_team.team_name]['zone_exits'] += 1
        return "ZONE_CLEAR"

    def _update_zone_time_stats(self, offensive_team, defensive_team):
        """Update zone time statistics."""
        time_increment = min(5, self.zone_time)  # Cap at 5 seconds per update
        
        # Update team stats
        self.team_stats[offensive_team.team_name]['zone_time_offensive'] += time_increment
        self.team_stats[defensive_team.team_name]['zone_time_defensive'] += time_increment
        
        # Update player stats for players on ice
        for player in self._get_on_ice(offensive_team):
            if player.id in self.game_stats:
                self.game_stats[player.id]['zone_time_offensive'] += time_increment
        
        for player in self._get_on_ice(defensive_team):
            if player.id in self.game_stats:
                self.game_stats[player.id]['zone_time_defensive'] += time_increment

    def _resolve_offensive_cycle(self, attacking_team, defending_team):
        """Resolve a cycling play in the offensive zone."""
        attacking_skaters = [p for p in self._get_on_ice(attacking_team) if p.primary_position != PlayerPosition.GOALIE]
        defending_skaters = [p for p in self._get_on_ice(defending_team) if p.primary_position != PlayerPosition.GOALIE]
        
        if not attacking_skaters or not defending_skaters:
            return self._zone_clear(defending_team)
        
        # Skill battle for maintaining possession
        att_skill = sum(p.puck_handling + p.passing + p.vision for p in attacking_skaters) / len(attacking_skaters)
        def_skill = sum(p.checking + p.defensive_awareness for p in defending_skaters) / len(defending_skaters)
        
        att_roll = att_skill + random.randint(-15, 15)
        def_roll = def_skill + random.randint(-15, 15)
        
        if att_roll > def_roll:
            # Successful cycle: work the puck -- someone gets open down low
            self._log_event(f"{attacking_team.team_name} maintains possession with cycling", "CYCLE")
            carrier = getattr(self, "possession_player", None) or random.choice(attacking_skaters)
            if random.random() < 0.65:
                res = self._attempt_pass(carrier, attacking_team, defending_team, kind="cycle")
                if res is not None and self.possession_team != attacking_team:
                    return "TURNOVER"
            self._shape_positions(attacking_team)
            self._emit_skate()
            return "CYCLE"
        else:
            # Turnover
            return self._turnover_possession(defending_team)

    def _maintain_offensive_possession(self, attacking_team):
        """Maintain possession in offensive zone."""
        self.possession_time += random.randint(3, 8)
        return "MAINTAIN_POSSESSION"

    def _attempt_zone_clear(self, defending_team, attacking_team):
        """Attempt to clear the puck from defensive zone."""
        defenders = [p for p in self._get_on_ice(defending_team) if p.primary_position != PlayerPosition.GOALIE]
        attackers = [p for p in self._get_on_ice(attacking_team) if p.primary_position != PlayerPosition.GOALIE]
        
        if not defenders:
            return "MAINTAIN_POSSESSION"
        
        # Find best clearing player
        best_defender = max(defenders, key=lambda p: p.passing + p.defensive_awareness + p.composure)
        
        # Pressure from forecheckers
        pressure = 0
        if attackers:
            best_forechecker = max(attackers, key=lambda p: p.checking + p.anticipation)
            pressure = best_forechecker.checking + best_forechecker.anticipation
        
        # Clear attempt
        clear_skill = best_defender.passing + best_defender.defensive_awareness + best_defender.composure
        fatigue_factor = self.player_fatigue.get(best_defender.id, 100) / 100
        
        clear_roll = clear_skill * fatigue_factor + random.randint(-10, 10)
        pressure_roll = pressure + random.randint(-5, 15)
        
        if clear_roll > pressure_roll:
            return self._zone_clear(defending_team)
        else:
            # Failed clear, maintain attack
            self._log_event(f"{best_defender.full_name}'s clear attempt is blocked", "FAILED_CLEAR")
            return "MAINTAIN_POSSESSION"

    def _attempt_breakout(self, attacking_team, defending_team):
        """Attempt to break out of defensive zone."""
        # This is when the "attacking" team is actually trying to get out of their own zone
        defenders = [p for p in self._get_on_ice(attacking_team) if p.primary_position != PlayerPosition.GOALIE]
        forecheckers = [p for p in self._get_on_ice(defending_team) if p.primary_position != PlayerPosition.GOALIE]
        
        if not defenders:
            return self._turnover_possession(defending_team)
        
        # Find best breakout player
        best_defender = max(defenders, key=lambda p: p.passing + p.first_pass + p.breakout_passes)
        
        # Forecheck pressure
        pressure = 0
        if forecheckers:
            pressure = sum(p.forechecking + p.checking for p in forecheckers[:2]) / 2  # Top 2 forecheckers
        
        # Breakout attempt
        breakout_skill = best_defender.passing + best_defender.first_pass + best_defender.vision
        fatigue_factor = self.player_fatigue.get(best_defender.id, 100) / 100
        
        breakout_roll = breakout_skill * fatigue_factor + random.randint(-10, 10)
        pressure_roll = pressure + random.randint(-5, 15)
        
        if breakout_roll > pressure_roll:
            self._log_event(f"{best_defender.full_name} completes the breakout", "BREAKOUT")
            self.current_zone = Zone.NEUTRAL_ZONE
            self.zone_time = 0
            return "BREAKOUT"
        else:
            # Failed breakout
            self._log_event(f"Breakout attempt by {best_defender.full_name} is pressured", "FAILED_BREAKOUT")
            return self._turnover_possession(defending_team)

    def _attempt_pass_entry(self, puck_carrier, attacking_team, defending_team):
        """Attempt a pass-based zone entry."""
        teammates = [p for p in self._get_on_ice(attacking_team) 
                    if p != puck_carrier and p.primary_position != PlayerPosition.GOALIE]
        
        if not teammates:
            return self._attempt_controlled_entry(puck_carrier, attacking_team, defending_team)
        
        target = random.choice(teammates)
        
        # Pass skill vs defensive awareness
        pass_skill = puck_carrier.passing + puck_carrier.vision
        
        defenders = [p for p in self._get_on_ice(defending_team) if p.primary_position != PlayerPosition.GOALIE]
        defensive_pressure = sum(p.defensive_awareness + p.anticipation for p in defenders) / len(defenders) if defenders else 0
        
        pass_roll = pass_skill + random.randint(-8, 8)
        defense_roll = defensive_pressure + random.randint(-8, 8)
        
        if pass_roll > defense_roll:
            self._log_event(f"{puck_carrier.full_name} finds {target.full_name} with a pass", "PASS_ENTRY")
            return self._successful_zone_entry(target, attacking_team, ZoneEntryType.PASS_IN)
        else:
            self._log_event(f"Pass by {puck_carrier.full_name} is intercepted", "TURNOVER")
            return self._turnover_possession(defending_team)

    def _attempt_chip_in(self, puck_carrier, attacking_team, defending_team):
        """Attempt a chip-in zone entry."""
        # Similar to dump-in but with more skill involved
        self._log_event(f"{puck_carrier.full_name} chips the puck into the zone", "CHIP_IN")
        
        # Enter offensive zone
        self.current_zone = Zone.OFFENSIVE_ZONE
        self.zone_time = 0
        
        # Higher chance of recovery than dump-in due to placement
        attacking_forwards = [p for p in self._get_on_ice(attacking_team) 
                             if p.primary_position in [PlayerPosition.LEFT_WING, PlayerPosition.CENTER, PlayerPosition.RIGHT_WING]]
        defending_dmen = [p for p in self._get_on_ice(defending_team) 
                         if p.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]]
        
        if attacking_forwards and defending_dmen:
            best_attacker = max(attacking_forwards, key=lambda p: p.skating + p.anticipation + p.hockey_iq)
            best_defender = max(defending_dmen, key=lambda p: p.defensive_awareness + p.anticipation)
            
            # Chip-in gives slight advantage to attacker
            att_roll = (best_attacker.skating + best_attacker.anticipation + best_attacker.hockey_iq) + 5
            def_roll = best_defender.defensive_awareness + best_defender.anticipation
            
            att_roll += random.randint(1, 10)
            def_roll += random.randint(1, 10)
            
            if att_roll > def_roll:
                self.possession_team = attacking_team
                self.possession_player = best_attacker
                self._log_event(f"{best_attacker.full_name} retrieves the chip-in", "PUCK_RECOVERY")
            else:
                return self._zone_clear(defending_team)

    def _resolve_loose_puck_battle(self):
        """A real puck battle: the nearest skater from each side converges
        on the loose puck and they fight for it (strength/balance/checking).
        The winner's team gets possession; support players collapse around."""
        self._ppos_ensure()
        px, py = self.puck_pos

        def nearest(team):
            sk = self._on_ice_skaters(team)
            if not sk:
                return None
            return min(sk, key=lambda p: self._ppos_dist(self._ppos_get(p), (px, py)))

        hb, ab = nearest(self.home_team), nearest(self.away_team)
        if hb is None and ab is None:
            return "FACEOFF"
        if hb is None or ab is None:
            winner = hb or ab
            loser = None
        else:
            hs = (hb.strength * 0.45 + hb.balance * 0.25 + hb.checking * 0.20
                  + hb.anticipation * 0.10 + random.randint(-6, 6))
            aws = (ab.strength * 0.45 + ab.balance * 0.25 + ab.checking * 0.20
                   + ab.anticipation * 0.10 + random.randint(-6, 6))
            winner, loser = (hb, ab) if hs >= aws else (ab, hb)
        wteam = self.home_team if winner.id in [p.id for p in self._get_on_ice(self.home_team)] \
            else self.away_team

        # both battlers converge on the puck; support collapses around it
        for b in (hb, ab):
            if b is not None:
                self._ppos_place(b, px, py, jitter=1.5)
        self.possession_team = wteam
        self.possession_player = winner
        self.possession_time = 0
        self.puck_pos = [px, py]

        self.game_stats[winner.id]['puck_battles_won'] += 1
        if loser is not None and loser.id in self.game_stats:
            self.game_stats[loser.id]['puck_battles_lost'] += 1
        self._log_event(f"{winner.full_name} wins the battle for the loose puck",
                        "PUCK_RECOVERY")
        self._emit_pbp("battle",
                       player_a=hb, player_b=ab, winner=winner,
                       puck_spot=(round(px, 1), round(py, 1)),
                       winner_team=wteam.team_name)
        self._shape_positions(wteam, (px, py))
        # keep the battlers at the pile
        for b in (hb, ab):
            if b is not None:
                self.player_positions[b.id] = [px, py]
        self._emit_skate()
        return "PUCK_RECOVERY"

    # ------------------------------------------------------------------
    # Positional tracking + off-puck play (drives the live visual sim)
    # Every on-ice skater has an (x, y) in rink coords (0-200 x, 0-85 y)
    # that follows what the sim is actually doing: formations, breakouts,
    # forechecks, battles. The UI tweens dots to these spots.
    # ------------------------------------------------------------------
    def _ppos_ensure(self):
        if not hasattr(self, "player_positions"):
            self.player_positions = {}   # player.id -> [x, y]
            self.puck_pos = [100.0, 42.5]
            self._last_skate_sent = {}

    @staticmethod
    def _ppos_role(p):
        pos = p.primary_position
        if pos == PlayerPosition.CENTER:
            return "C"
        if pos == PlayerPosition.LEFT_WING:
            return "LW"
        if pos == PlayerPosition.RIGHT_WING:
            return "RW"
        if pos == PlayerPosition.GOALIE:
            return "G"
        return "D"

    def _ppos_get(self, p):
        self._ppos_ensure()
        return self.player_positions.get(getattr(p, "id", None), [100.0, 42.5])

    @staticmethod
    def _ppos_dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    def _ppos_place(self, p, x, y, jitter=2.5):
        x += random.uniform(-jitter, jitter)
        y += random.uniform(-jitter, jitter)
        self.player_positions[p.id] = [min(196.0, max(4.0, x)),
                                       min(81.0, max(4.0, y))]

    def _on_ice_skaters(self, team):
        return [p for p in self._get_on_ice(team) if self._ppos_role(p) != "G"]

    def _on_ice_goalie(self, team):
        for p in self._get_on_ice(team):
            if self._ppos_role(p) == "G":
                return p
        return None

    def _shape_positions(self, attacking_team, puck=None):
        """Position both on-ice units for the current situation.

        attacking_team: team with possession (or pressing). puck: (x, y).
        Shapes: attack (ozone setup), breakout (own end), neutral,
        dzone (defending), forecheck.
        """
        self._ppos_ensure()
        if puck is None:
            puck = self.puck_pos
        px, py = puck
        defending_team = (self.away_team if attacking_team == self.home_team
                          else self.home_team)
        carrier = getattr(self, "possession_player", None)
        carrier_id = getattr(carrier, "id", None)

        for team in (attacking_team, defending_team):
            is_att = (team == attacking_team)
            adir = 1 if team == self.home_team else -1  # direction team attacks
            att_net = 189.0 if adir == 1 else 11.0     # net this team attacks
            def_net = 11.0 if adir == 1 else 189.0     # net this team defends
            # where is the puck relative to this team?
            deep_off = (adir == 1 and px > 125) or (adir == -1 and px < 75)
            deep_def = (adir == 1 and px < 75) or (adir == -1 and px > 125)
            if is_att:
                shape = "attack" if deep_off else ("breakout" if deep_def else "neutral")
            else:
                shape = "dzone" if deep_def else ("forecheck" if deep_off else "neutral")

            skaters = self._on_ice_skaters(team)
            by_role = {"C": [], "W": [], "D": []}
            for p in skaters:
                r = self._ppos_role(p)
                by_role["C" if r == "C" else "W" if r in ("LW", "RW") else "D"].append(p)
            centers, wings, ds = by_role["C"], by_role["W"], by_role["D"]

            if shape == "attack":
                spots = {"C": [(att_net - 24 * adir, 42.5)],
                         "W": [(att_net - 36 * adir, 22.0), (att_net - 36 * adir, 63.0)],
                         "D": [(att_net - 54 * adir, 30.0), (att_net - 54 * adir, 55.0)]}
            elif shape == "breakout":
                spots = {"C": [(def_net + 20 * adir, 42.5)],
                         "W": [(def_net + 34 * adir, 22.0), (def_net + 34 * adir, 63.0)],
                         "D": [(def_net + 8 * adir, 42.5), (def_net + 28 * adir, 42.5)]}
            elif shape == "dzone":
                spots = {"C": [(def_net + 26 * adir, 42.5)],
                         "W": [(def_net + 32 * adir, 24.0), (def_net + 32 * adir, 61.0)],
                         "D": [(def_net + 14 * adir, 36.0), (def_net + 14 * adir, 49.0)]}
            elif shape == "forecheck":
                spots = {"C": [(px - 10 * adir, 42.5)],
                         "W": [(px - 10 * adir, 28.0), (px - 10 * adir, 57.0)],
                         "D": [(px - 32 * adir, 32.0), (px - 32 * adir, 53.0)]}
                # F1 hunts the puck
                if centers:
                    spots["C"] = [(px, py)]
            else:  # neutral: lanes stretched through the middle
                spots = {"C": [(px + 2 * adir, 42.5)],
                         "W": [(px + 10 * adir, 25.0), (px + 10 * adir, 60.0)],
                         "D": [(px - 14 * adir, 32.0), (px - 14 * adir, 53.0)]}

            for p in centers[:1]:
                self._ppos_place(p, *spots["C"][0])
            for p, s in zip(wings, spots["W"]):
                self._ppos_place(p, *s)
            for p, s in zip(ds, spots["D"]):
                self._ppos_place(p, *s)
            # extras (odd-man units) fill nearest free spot
            extras = centers[1:] + wings[2:] + ds[2:]
            for p in extras:
                self._ppos_place(p, px - 18 * adir, 42.5)
            # puck carrier skates with the puck
            if carrier_id and is_att:
                for p in skaters:
                    if p.id == carrier_id:
                        self._ppos_place(p, px, py, jitter=1.0)
            # goalie holds his net, shuffling with the puck
            g = self._on_ice_goalie(team)
            if g is not None:
                self._ppos_place(g, def_net, 42.5 + max(-9.0, min(9.0, (py - 42.5) * 0.3)),
                                 jitter=0.5)

    def _emit_skate(self, force=False):
        """Send position snapshot to visual listeners if anyone moved."""
        self._ppos_ensure()
        if not self.pbp_listeners:
            return
        snap, changed = {}, force
        for team in (self.home_team, self.away_team):
            for p in self._get_on_ice(team):
                x, y = self.player_positions.get(p.id, (100.0, 42.5))
                snap[p.id] = (round(x, 1), round(y, 1))
                old = self._last_skate_sent.get(p.id)
                if old is None or abs(old[0] - x) > 6 or abs(old[1] - y) > 6:
                    changed = True
        if changed:
            self._last_skate_sent = dict(snap)
            carrier = getattr(self, "possession_player", None)
            self._emit_pbp("skate", positions=snap,
                           puck=(round(self.puck_pos[0], 1), round(self.puck_pos[1], 1)),
                           possession_player=getattr(carrier, "id", None))

    def _faceoff_formation(self, winner, zone):
        """Line everyone up for the draw, then tell the visual sim."""
        self._ppos_ensure()
        wdir = 1 if winner == self.home_team else -1   # direction winner attacks
        wnet = 189.0 if wdir == 1 else 11.0
        # dot: neutral -> center ice; else the relevant end-zone dot
        if zone == FaceoffZone.NEUTRAL_ZONE:
            dx, dy = 100.0, 42.5
        else:
            # offensive-zone draw ~20 ft outside the attacked net, else own end
            nx = wnet - 20 * wdir if zone == FaceoffZone.OFFENSIVE_ZONE else (11.0 if wdir == 1 else 189.0) + 20 * wdir
            dx, dy = nx, random.choice((20.5, 64.5))
        loser = self.away_team if winner == self.home_team else self.home_team
        for team in (winner, loser):
            won = (team == winner)
            tdir = wdir if won else -wdir
            skaters = self._on_ice_skaters(team)
            centers = [p for p in skaters if self._ppos_role(p) == "C"]
            wings = [p for p in skaters if self._ppos_role(p) in ("LW", "RW")]
            ds = [p for p in skaters if self._ppos_role(p) == "D"]
            if centers:
                self._ppos_place(centers[0], dx - (2 if won else -2), dy, jitter=0.5)
            for p, s in zip(wings, (-9, 9)):
                self._ppos_place(p, dx + (0 if won else 6 * tdir), dy + s, jitter=1.0)
            for p, s in zip(ds, (30, 55)):
                # D hold back toward their own end
                own = 11.0 if team == self.home_team else 189.0
                bx = dx + (24 if (own < dx) else -24)
                self._ppos_place(p, bx, s, jitter=1.5)
            for p in centers[1:] + wings[2:] + ds[2:]:
                self._ppos_place(p, dx + 18 * tdir, 42.5)
            g = self._on_ice_goalie(team)
            if g is not None:
                own = 11.0 if team == self.home_team else 189.0
                self._ppos_place(g, own, 42.5, jitter=0.5)
        self.puck_pos = [dx, dy]
        self._emit_skate(force=True)

    def _nearest_defender(self, player, defenders):
        px, py = self._ppos_get(player)
        best, bd = None, 1e9
        for d in defenders:
            dd = self._ppos_dist((px, py), self._ppos_get(d))
            if dd < bd:
                best, bd = d, dd
        return best, bd

    def _attempt_pass(self, passer, attacking_team, defending_team, kind="cycle"):
        """A real pass with off-puck play.

        Each potential receiver first battles his coverage to get open
        (offensive awareness + agility vs defensive awareness + anticipation).
        Winners shake to space; the passer then picks a target and the pass
        is completed or picked off. Returns the receiver, the interceptor,
        or None.
        """
        self._ppos_ensure()
        mates = [p for p in self._on_ice_skaters(attacking_team) if p.id != passer.id]
        if not mates:
            return None
        defenders = self._on_ice_skaters(defending_team)
        adir = 1 if attacking_team == self.home_team else -1
        att_net = 189.0 if adir == 1 else 11.0
        px, py = self._ppos_get(passer)

        # --- off-puck battle: get open ---
        cands = []
        for m in mates:
            mx, my = self._ppos_get(m)
            nd, dd = self._nearest_defender(m, defenders)
            off = m.offensive_awareness + m.agility + random.randint(-8, 8)
            dfn = (nd.defensive_awareness + nd.anticipation + random.randint(-8, 8)) \
                if nd is not None else -99
            got_open = off > dfn
            if got_open and nd is not None:
                # shake the checker: step away into space, drift dangerous
                nx_, ny_ = self._ppos_get(nd)
                ang = math.atan2(my - ny_, mx - nx_)
                mx2 = mx + math.cos(ang) * 7 + (adir * 4 if kind in ("cycle", "attack") else 0)
                my2 = my + math.sin(ang) * 7
                self._ppos_place(m, mx2, my2, jitter=1.0)
                mx, my = self.player_positions[m.id]
                dd = self._ppos_dist((mx, my), self._ppos_get(nd))
            fwd = (mx - px) * adir
            danger = -abs(mx - att_net) / 10.0
            score = ((14 if got_open else 0) + dd * 0.6 + fwd * 0.25 + danger
                     + random.uniform(0, 4))
            cands.append((score, m, mx, my, nd, dd, got_open))
        cands.sort(key=lambda t: -t[0])
        _, receiver, rx, ry, nd, dd, got_open = cands[0]

        # --- pass execution ---
        lane_pressure = max(0.0, 10.0 - dd) if nd is not None else 0.0
        q = (52 + passer.passing * 1.0 + min(dd, 10.0) * 1.2
             - lane_pressure * 3.0)
        q = max(10.0, min(95.0, q))
        completed = random.uniform(0, 100) < q
        interceptor = None
        if not completed and defenders:
            mid = ((px + rx) / 2.0, (py + ry) / 2.0)
            interceptor = min(defenders,
                              key=lambda d: self._ppos_dist(mid, self._ppos_get(d)))

        self._emit_pbp("pass",
                       passer=passer, receiver=receiver,
                       passer_pos=(round(px, 1), round(py, 1)),
                       receiver_pos=(round(rx, 1), round(ry, 1)),
                       completed=completed, got_open=got_open,
                       interceptor=interceptor,
                       attacking_team=attacking_team.team_name,
                       kind=kind)
        if completed:
            self.possession_player = receiver
            self.puck_pos = [rx, ry]
            self._emit_skate()
            return receiver
        if interceptor is not None:
            self._resolve_turnover(passer, interceptor, TurnoverType.INTERCEPTION)
        else:
            self._turnover_possession(defending_team)
        self._emit_skate()
        return interceptor

    def _is_on_penalty_kill(self, player):
        """Check if player is on penalty kill."""
        team = self.home_team if player in self.home_on_ice else self.away_team
        opposing_team = self.away_team if team == self.home_team else self.home_team
        
        team_penalties = self.home_penalties if team == self.home_team else self.away_penalties
        opposing_penalties = self.away_penalties if team == self.home_team else self.home_penalties
        
        return len(opposing_penalties) > len(team_penalties)

    def _is_on_power_play(self, player):
        """Check if player is on power play."""
        team = self.home_team if player in self.home_on_ice else self.away_team
        
        team_penalties = self.home_penalties if team == self.home_team else self.away_penalties
        opposing_penalties = self.away_penalties if team == self.home_team else self.home_penalties
        
        return len(team_penalties) > len(opposing_penalties)
        """Determines and resolves the next gameplay event."""
        attacking_skaters = [p for p in self._get_on_ice(attacking_team) if p.primary_position != PlayerPosition.GOALIE]
        defending_skaters = [p for p in self._get_on_ice(defending_team) if p.primary_position != PlayerPosition.GOALIE]

        if not attacking_skaters or not defending_skaters:
            return "Turnover", self._resolve_faceoff()

        attacker = random.choice(attacking_skaters)
        defender = random.choice(defending_skaters)

        attacker_roll = attacker.skating + attacker.deking + attacker.offensive_awareness + random.randint(-10, 10)
        defender_roll = defender.checking + defender.strength + defender.defensive_awareness + random.randint(-10, 10)

        if attacker_roll > defender_roll:
            self._resolve_scoring_chance(attacker, attacking_team, defending_team)
            return "Scoring Chance", attacking_team 
        else:
            if random.random() < (defender.hitting_tendency / 1000.0) and (20 - defender.discipline) > random.randint(1, 20):
                self._resolve_penalty(defender, defending_team)
                return "Penalty", attacking_team 
            
            self._log_event(f"{defender.full_name} breaks up the play.", "TURNOVER")
            return "Turnover", defending_team

    def _resolve_scoring_chance(self, shooter, attacking_team, defending_team):
        """
        Stage 1 Enhancement: Resolves a shot attempt with detailed tracking.
        Determines shot type, location, quality, and whether it's blocked, missed, or on goal.
        """
        # Determine shot location based on player position and situation
        shot_location = self._determine_shot_location(shooter, attacking_team)
        
        # Calculate distance from goal (affects shot quality)
        distance = self._calculate_shot_distance(shot_location)
        
        # Check for blocked shot first
        blocking_outcome = self._check_shot_blocking(shooter, defending_team, shot_location)
        if blocking_outcome['blocked']:
            self._handle_blocked_shot(shooter, blocking_outcome['blocker'], attacking_team, defending_team)
            return
        
        # Determine shot type based on player attributes and situation
        shot_type = self._determine_shot_type(shooter, shot_location, distance)
        
        # Calculate shot quality (high/medium/low danger)
        shot_quality = self._calculate_shot_quality(shot_location, distance, shot_type, attacking_team)
        
        # Check if shot misses the net
        if self._check_shot_miss(shooter, shot_quality, distance):
            self._handle_missed_shot(shooter, attacking_team, shot_location, shot_type)
            return
        
        # Shot is on goal - resolve against goalie
        self._resolve_shot_on_goal(shooter, attacking_team, defending_team, shot_type, shot_location, shot_quality, distance)

    def _determine_shot_location(self, shooter, attacking_team):
        """Determine where the shot is taken from based on player position and game flow."""
        # Simplified location determination - can be enhanced further
        location_weights = {
            ShotLocation.HIGH_SLOT: 0.25,
            ShotLocation.LOW_SLOT: 0.20,
            ShotLocation.LEFT_CIRCLE: 0.15,
            ShotLocation.RIGHT_CIRCLE: 0.15,
            ShotLocation.POINT: 0.10,
            ShotLocation.LEFT_WING: 0.08,
            ShotLocation.RIGHT_WING: 0.05,
            ShotLocation.CREASE: 0.02
        }
        
        # Adjust weights based on player position
        if shooter.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]:
            location_weights[ShotLocation.POINT] *= 3
            location_weights[ShotLocation.HIGH_SLOT] *= 0.5
        elif shooter.primary_position == PlayerPosition.CENTER:
            location_weights[ShotLocation.HIGH_SLOT] *= 1.5
            location_weights[ShotLocation.LOW_SLOT] *= 1.3
        
        return self._weighted_random_choice(location_weights)

    def _calculate_shot_distance(self, location):
        """Calculate approximate distance from goal in feet."""
        distance_map = {
            ShotLocation.CREASE: 6,
            ShotLocation.LOW_SLOT: 15,
            ShotLocation.HIGH_SLOT: 25,
            ShotLocation.LEFT_CIRCLE: 30,
            ShotLocation.RIGHT_CIRCLE: 30,
            ShotLocation.LEFT_WING: 35,
            ShotLocation.RIGHT_WING: 35,
            ShotLocation.POINT: 50,
            ShotLocation.BEHIND_NET: 10
        }
        return distance_map.get(location, 30) + random.randint(-3, 3)

    def _check_shot_blocking(self, shooter, defending_team, location):
        """
        Stage 4 Enhancement: Check if the shot gets blocked by a defending player with detailed tracking.
        """
        defending_skaters = [p for p in self._get_on_ice(defending_team) if p.primary_position != PlayerPosition.GOALIE]
        
        if not defending_skaters:
            return {'blocked': False, 'blocker': None}
        
        # Higher chance of blocks from closer to goal
        base_block_chance = {
            ShotLocation.CREASE: 0.4,
            ShotLocation.LOW_SLOT: 0.3,
            ShotLocation.HIGH_SLOT: 0.2,
            ShotLocation.LEFT_CIRCLE: 0.15,
            ShotLocation.RIGHT_CIRCLE: 0.15,
            ShotLocation.POINT: 0.25,
            ShotLocation.LEFT_WING: 0.1,
            ShotLocation.RIGHT_WING: 0.1
        }.get(location, 0.1)
        
        # Apply defensive system modifier (Stage 4)
        if self.current_defensive_system == DefensiveSystem.DEFENSIVE_SHELL:
            base_block_chance *= 1.2
        elif self.current_defensive_system == DefensiveSystem.AGGRESSIVE_FORECHECK:
            base_block_chance *= 0.9
        
        # Apply defensive pressure modifier (Stage 4)
        base_block_chance *= self.defensive_pressure
        
        # Choose the blocker by weighted draw: attributes x archetype block
        # tendency, so defensive D/grinders block most but not exclusively.
        best_blocker = self._weighted_skater_choice(defending_skaters, "block")
        if best_blocker is None:
            return {'blocked': False, 'blocker': None}
        
        # Calculate block probability with Stage 4 enhancements
        blocker_skill = (best_blocker.defensive_awareness + best_blocker.checking + best_blocker.anticipation + best_blocker.positioning) / 4
        shooter_skill = (shooter.shooting_accuracy + shooter.shooting_power) / 2
        
        block_chance = base_block_chance * (blocker_skill / max(shooter_skill, 1))
        # Archetype tendency: defensive defensemen and grinders sell out to
        # block; snipers and offensive defensemen rarely do.
        try:
            block_chance *= get_tendency(best_blocker, "block")
        except Exception:
            pass
        block_chance = min(block_chance, 0.5)  # Cap at 50%
        
        if random.random() < block_chance:
            # Record defensive play (Stage 4)
            self._record_defensive_success(best_blocker, DefensiveAction.SHOT_BLOCK)
            return {'blocked': True, 'blocker': best_blocker}
        
        return {'blocked': False, 'blocker': None}

    def _determine_shot_type(self, shooter, location, distance):
        """Determine the type of shot based on player attributes and situation."""
        # Base probabilities
        type_weights = {
            ShotType.WRIST_SHOT: 0.4,
            ShotType.SNAP_SHOT: 0.25,
            ShotType.SLAP_SHOT: 0.15,
            ShotType.BACKHAND: 0.1,
            ShotType.TIP_IN: 0.05,
            ShotType.WRAPAROUND: 0.03,
            ShotType.DEFLECTION: 0.01,
            ShotType.REBOUND: 0.01
        }
        
        # Adjust based on distance
        if distance > 40:
            type_weights[ShotType.SLAP_SHOT] *= 2
            type_weights[ShotType.WRIST_SHOT] *= 0.7
        elif distance < 15:
            type_weights[ShotType.TIP_IN] *= 3
            type_weights[ShotType.BACKHAND] *= 2
            type_weights[ShotType.SLAP_SHOT] *= 0.3
        
        # Adjust based on location
        if location in [ShotLocation.CREASE, ShotLocation.LOW_SLOT]:
            type_weights[ShotType.TIP_IN] *= 2
            type_weights[ShotType.REBOUND] *= 2
        elif location == ShotLocation.POINT:
            type_weights[ShotType.SLAP_SHOT] *= 2.5
        
        return self._weighted_random_choice(type_weights)

    def _calculate_shot_quality(self, location, distance, shot_type, attacking_team):
        """Calculate shot quality (high/medium/low danger) and return quality score."""
        base_quality = {
            ShotLocation.CREASE: 0.9,
            ShotLocation.LOW_SLOT: 0.8,
            ShotLocation.HIGH_SLOT: 0.6,
            ShotLocation.LEFT_CIRCLE: 0.5,
            ShotLocation.RIGHT_CIRCLE: 0.5,
            ShotLocation.LEFT_WING: 0.3,
            ShotLocation.RIGHT_WING: 0.3,
            ShotLocation.POINT: 0.2
        }.get(location, 0.4)
        
        # Adjust for shot type
        type_modifier = {
            ShotType.TIP_IN: 1.3,
            ShotType.REBOUND: 1.4,
            ShotType.DEFLECTION: 1.2,
            ShotType.WRIST_SHOT: 1.0,
            ShotType.SNAP_SHOT: 1.1,
            ShotType.SLAP_SHOT: 0.9,
            ShotType.BACKHAND: 0.8,
            ShotType.WRAPAROUND: 1.1
        }.get(shot_type, 1.0)
        
        # Distance penalty
        distance_modifier = max(0.3, 1.0 - (distance - 10) * 0.02)
        
        quality_score = base_quality * type_modifier * distance_modifier
        
        # Categorize danger level
        if quality_score >= 0.7:
            return "high"
        elif quality_score >= 0.4:
            return "medium"
        else:
            return "low"

    def _check_shot_miss(self, shooter, quality, distance):
        """Check if shot misses the net entirely."""
        accuracy = (shooter.shooting_accuracy + shooter.composure) / 2
        
        # Base miss chance
        base_miss = 0.15
        
        # Adjust for distance
        distance_penalty = distance * 0.005
        
        # Adjust for quality
        quality_modifier = {"high": 0.7, "medium": 1.0, "low": 1.4}[quality]
        
        miss_chance = base_miss + distance_penalty
        miss_chance *= quality_modifier
        miss_chance *= (20 - accuracy) / 20  # Better accuracy = lower miss chance
        
        return random.random() < miss_chance

    def _weighted_random_choice(self, weights_dict):
        """Helper method to make weighted random choices."""
        items = list(weights_dict.keys())
        weights = list(weights_dict.values())
        total = sum(weights)
        
        r = random.uniform(0, total)
        upto = 0
        for item, weight in zip(items, weights):
            if upto + weight >= r:
                return item
            upto += weight
        return items[-1]  # Fallback

    def _weighted_skater_choice(self, skaters, tendency_key):
        """Pick a skater weighted by archetype behavioral tendency.

        E.g. "shoot" makes snipers the shooter far more often than
        playmakers; "hit" makes power forwards/enforcers throw the hits.
        Falls back to uniform choice if anything goes wrong.
        """
        if not skaters:
            return None
        try:
            weights = [max(0.05, get_tendency(p, tendency_key)) for p in skaters]
            return random.choices(skaters, weights=weights, k=1)[0]
        except Exception:
            return random.choice(skaters)

    def _handle_blocked_shot(self, shooter, blocker, attacking_team, defending_team):
        """Handle a blocked shot event with proper stat tracking."""
        # Update player stats
        self.game_stats[shooter.id]['shot_attempts'] += 1
        self.game_stats[shooter.id]['blocked_shots'] += 1
        self.game_stats[blocker.id]['shots_blocked'] += 1
        
        # Update team stats
        att_team_name = attacking_team.team_name
        def_team_name = defending_team.team_name
        
        self.team_stats[att_team_name]['shot_attempts'] += 1
        self.team_stats[att_team_name]['blocked_shots'] += 1
        self.team_stats[def_team_name]['shots_blocked'] += 1
        
        # Corsi tracking
        self.game_stats[shooter.id]['corsi_for'] += 1
        for player in self._get_on_ice(defending_team):
            if player.id in self.game_stats:
                self.game_stats[player.id]['corsi_against'] += 1
        
        self.team_stats[att_team_name]['corsi_for'] += 1
        self.team_stats[def_team_name]['corsi_against'] += 1
        
        self._log_event(f"Shot by {shooter.full_name} blocked by {blocker.full_name}!", "BLOCKED_SHOT")
        self._emit_pbp("blocked_shot",
                       shooter=shooter,
                       blocker=blocker,
                       attacking_team=attacking_team.team_name,
                       defending_team=defending_team.team_name)
        # Loose puck off the block -- both teams scramble for it
        if random.random() < 0.55:
            self._ppos_ensure()
            bx, by = self._ppos_get(blocker)
            self.puck_pos = [bx, by]
            self.possession_team = None
            self.possession_player = None
            self.possession_time = 0

    def _handle_missed_shot(self, shooter, attacking_team, location, shot_type):
        """Handle a missed shot event."""
        # Update player stats
        self.game_stats[shooter.id]['shot_attempts'] += 1
        self.game_stats[shooter.id]['missed_shots'] += 1
        
        # Update team stats
        att_team_name = attacking_team.team_name
        self.team_stats[att_team_name]['shot_attempts'] += 1
        
        # Corsi tracking
        self.game_stats[shooter.id]['corsi_for'] += 1
        self.team_stats[att_team_name]['corsi_for'] += 1
        
        self._log_event(f"Shot by {shooter.full_name} misses the net!", "MISSED_SHOT")
        self._emit_pbp("missed_shot",
                       shooter=shooter,
                       attacking_team=attacking_team.team_name,
                       shot_type=shot_type.value if hasattr(shot_type, "value") else str(shot_type),
                       location=location.value if hasattr(location, "value") else str(location))
        # Missed shot rims around -- loose puck battle behind the net
        if random.random() < 0.40:
            self._ppos_ensure()
            nx = 189.0 if attacking_team == self.home_team else 11.0
            self.puck_pos = [min(196.0, max(4.0, nx + random.uniform(-8, 8))),
                             min(81.0, max(4.0, 42.5 + random.uniform(-14, 14)))]
            self.possession_team = None
            self.possession_player = None
            self.possession_time = 0

    def _apply_archetype_matchup(self, quality, attacking_team, defending_team):
        """
        Archetype matchup effects on shot quality.

        Compares the on-ice attacking skaters' archetypes against the
        defending skaters' archetypes (e.g. Defensive Defenseman vs Sniper)
        and returns an adjusted quality value.
        """
        try:
            att = [p for p in self._get_on_ice(attacking_team)
                   if p.primary_position != PlayerPosition.GOALIE]
            dfn = [p for p in self._get_on_ice(defending_team)
                   if p.primary_position != PlayerPosition.GOALIE]
            if not att or not dfn:
                return quality
            mult = matchup_multiplier([get_archetype(p) for p in att],
                                      [get_archetype(p) for p in dfn])
            return quality * mult
        except Exception:
            return quality

    def _resolve_shot_on_goal(self, shooter, attacking_team, defending_team, shot_type, location, quality, distance):
        """
        Stage 5: Enhanced shot resolution with advanced goaltending excellence.
        """
        goalie = defending_team.get_starting_goalie()
        
        # Handle passing play possibility
        passer = None
        # Archetype tendency: snipers shoot first, playmakers look pass first.
        # shoot_pass_tendency is SHOOT tendency (high = shooter), so the pass
        # branch scales with (100 - tendency) and inversely with shoot_bias.
        shoot_bias = get_tendency(shooter, "shoot_bias")
        pass_bias = 1.0 / shoot_bias if shoot_bias else 1.0
        pass_chance = min(100.0, (100 - shooter.shoot_pass_tendency) * pass_bias)
        if random.random() * 100 < pass_chance \
                and shot_type not in [ShotType.REBOUND, ShotType.TIP_IN]:
            teammates = [p for p in self._get_on_ice(attacking_team) if p != shooter and p.primary_position != PlayerPosition.GOALIE]
            if teammates and random.random() < 0.3:  # 30% chance of pass play
                passer = shooter
                shooter = random.choice(teammates)
                self._log_event(f"Pass from {passer.full_name} to {shooter.full_name}...", "PASS")
        
        # Calculate expected goal value (xG)
        # Archetype matchup effects: shutdown defenders smother snipers,
        # power forwards feast on soft defensive pairs, etc.
        quality = self._apply_archetype_matchup(
            quality, attacking_team, defending_team)
        expected_goal = self._calculate_expected_goal_value(location, shot_type, quality, distance)

        # Team tactics shape finishing: systems and special-teams approach
        # move xG up/down for both sides.
        expected_goal = min(0.95, expected_goal * self._team_tactics_xg_factor(
            attacking_team, defending_team))

        # Update expected goals tracking
        self.expected_goals[attacking_team.team_name] = \
            self.expected_goals.get(attacking_team.team_name, 0.0) + expected_goal

        self._emit_pbp("shot",
                       shooter=shooter,
                       passer=passer,
                       attacking_team=attacking_team.team_name,
                       defending_team=defending_team.team_name,
                       shot_type=shot_type.value if hasattr(shot_type, "value") else str(shot_type),
                       location=location.value if hasattr(location, "value") else str(location),
                       quality=self._pbp_num(quality),
                       distance=self._pbp_num(distance))
        # Positional: the shot heads for the net
        self._ppos_ensure()
        self.puck_pos = [189.0 if attacking_team == self.home_team else 11.0, 42.5]
        
        # Determine goaltender positioning and style
        self._adjust_goaltender_positioning(goalie, location, self.current_situation)
        goalie_style = self._determine_goaltender_style(goalie)
        goalie_position = self.goaltender_positioning.get(goalie.id, GoaltenderPosition.IN_NET)
        
        # Calculate save probability with advanced goaltending model
        save_probability = self._calculate_save_probability(
            goalie, location, shot_type, quality, distance, expected_goal
        )
        
        # Add passing bonus to shot skill
        shot_skill_bonus = 0
        if passer:
            shot_skill_bonus = passer.passing * 0.3
        
        # Determine save type
        save_type = self._get_save_type(location, shot_type, goalie_position, goalie_style)
        
        # Update shot statistics regardless of outcome
        self._update_shot_stats(shooter, attacking_team, defending_team, quality, distance, shot_type)
        
        # Apply shot skill bonus to save probability
        adjusted_save_prob = save_probability * (1.0 - (shot_skill_bonus / 200))  # Slight reduction for good passes
        
        # Resolve the shot
        if random.random() > adjusted_save_prob:
            # Goal scored
            goal_type = self._determine_goal_type(shot_type, location, save_type)
            
            # Record the goal
            self._record_goaltender_stats(goalie, 'goal', save_type, expected_goal, quality)
            
            # Handle assists
            assists = []
            if passer:
                assists.append(passer)
            if random.random() < 0.4:  # Secondary assist chance
                second_assist_candidates = [p for p in self._get_on_ice(attacking_team) 
                                          if p not in [shooter, passer] and p.primary_position != PlayerPosition.GOALIE]
                if second_assist_candidates:
                    assists.append(random.choice(second_assist_candidates))
            
            self._handle_goal(attacking_team, shooter, assists, shot_type, location)
            
            # Log advanced goal details
            self.event_log.append({
                'timestamp': self._period_length - self.clock,
                'duration': 1.0,
                'type': 'GOAL_ADVANCED',
                'details': {
                    'scorer_id': shooter.id,
                    'goaltender_id': goalie.id,
                    'goal_type': goal_type.value,
                    'expected_goal': round(expected_goal, 3),
                    'save_probability': round(adjusted_save_prob, 3),
                    'shot_quality': quality
                }
            })
        else:
            # Save made
            shot_power = random.randint(1, 10)  # Shot power factor
            rebound_control = self._determine_rebound_control(goalie, save_type, shot_type, shot_power)
            
            # Record the save
            self._record_goaltender_stats(goalie, 'save', save_type, expected_goal, quality)
            
            # Handle rebound outcome
            if rebound_control in [ReboundControl.WEAK_REBOUND, ReboundControl.DANGEROUS_REBOUND]:
                # Create a rebound opportunity
                self._resolve_rebound_chance(attacking_team, defending_team)
            else:
                # Regular save
                self._handle_save(goalie, shooter, shot_type, quality)
            
            # Update goaltender fatigue
            self._update_goaltender_fatigue(goalie, quality)
            
            # Log advanced save details
            self.event_log.append({
                'timestamp': self._period_length - self.clock,
                'duration': 0.5,
                'type': 'SAVE_ADVANCED',
                'details': {
                    'shooter_id': shooter.id,
                    'goaltender_id': goalie.id,
                    'save_type': save_type.value,
                    'rebound_control': rebound_control.value,
                    'expected_goal': round(expected_goal, 3),
                    'save_probability': round(adjusted_save_prob, 3),
                    'shot_quality': quality
                }
            })

    def _calculate_shooter_skill(self, shooter, shot_type, quality, distance):
        """Calculate the shooter's skill for this specific shot."""
        base_skill = (
            shooter.shooting_accuracy * 0.3 +
            shooter.shooting_power * 0.2 +
            shooter.composure * 0.15 +
            shooter.offensive_awareness * 0.15 +
            shooter.hockey_iq * 0.1 +
            shooter.flair * 0.1
        )
        
        # Shot type modifiers
        type_bonus = {
            ShotType.WRIST_SHOT: shooter.shooting_accuracy * 0.1,
            ShotType.SLAP_SHOT: shooter.shooting_power * 0.15,
            ShotType.SNAP_SHOT: (shooter.shooting_accuracy + shooter.shooting_power) * 0.05,
            ShotType.TIP_IN: shooter.anticipation * 0.2,
            ShotType.REBOUND: shooter.anticipation * 0.15,
            ShotType.DEFLECTION: shooter.anticipation * 0.1,
            ShotType.BACKHAND: shooter.deking * 0.1,
            ShotType.WRAPAROUND: shooter.deking * 0.15
        }.get(shot_type, 0)
        
        # Quality bonus
        quality_bonus = {"high": 5, "medium": 2, "low": 0}[quality]
        
        return base_skill + type_bonus + quality_bonus

    def _calculate_goalie_skill(self, goalie, shot_type, location, quality):
        """Calculate goalie's skill for stopping this specific shot (legacy method for compatibility)."""
        base_skill = (
            goalie.goaltending * 0.4 +
            goalie.reflexes * 0.2 +
            goalie.positioning * 0.15 +
            goalie.rebound_control * 0.1 +
            goalie.composure * 0.1 +
            goalie.anticipation * 0.05
        )
        
        # Location-based adjustments
        location_modifier = {
            ShotLocation.CREASE: -5,
            ShotLocation.LOW_SLOT: -3,
            ShotLocation.HIGH_SLOT: 0,
            ShotLocation.LEFT_CIRCLE: 1,
            ShotLocation.RIGHT_CIRCLE: 1,
            ShotLocation.POINT: 3,
            ShotLocation.LEFT_WING: 2,
            ShotLocation.RIGHT_WING: 2
        }.get(location, 0)
        
        # Shot type modifiers
        type_modifier = {
            ShotType.TIP_IN: -4,
            ShotType.DEFLECTION: -3,
            ShotType.REBOUND: -2,
            ShotType.WRAPAROUND: -1,
            ShotType.SLAP_SHOT: 1,
            ShotType.WRIST_SHOT: 0,
            ShotType.SNAP_SHOT: 0,
            ShotType.BACKHAND: 1
        }.get(shot_type, 0)
        
        return base_skill + location_modifier + type_modifier

    def _update_shot_stats(self, shooter, attacking_team, defending_team, quality, distance, shot_type):
        """Update all relevant statistics for a shot on goal."""
        # Player stats
        self.game_stats[shooter.id]['shots_on_goal'] += 1
        self.game_stats[shooter.id]['shot_attempts'] += 1
        self.game_stats[shooter.id]['shot_distance_total'] += distance
        
        # Quality tracking
        quality_key = f"{quality}_danger_shots"
        self.game_stats[shooter.id][quality_key] += 1
        
        # Team stats
        att_team_name = attacking_team.team_name
        def_team_name = defending_team.team_name
        
        self.team_stats[att_team_name]['shots_on_goal'] += 1
        self.team_stats[att_team_name]['shot_attempts'] += 1
        
        if quality == "high":
            self.team_stats[att_team_name]['high_danger_chances'] += 1
        
        # Corsi tracking
        self.game_stats[shooter.id]['corsi_for'] += 1
        for player in self._get_on_ice(defending_team):
            if player.id in self.game_stats:
                self.game_stats[player.id]['corsi_against'] += 1
        
        self.team_stats[att_team_name]['corsi_for'] += 1
        self.team_stats[def_team_name]['corsi_against'] += 1

    def _check_rebound_created(self, goalie, shot_type):
        """Check if the save creates a rebound opportunity (legacy compatibility method)."""
        base_rebound_chance = 0.25
        
        # Shot type affects rebound chance
        type_modifier = {
            ShotType.SLAP_SHOT: 1.3,
            ShotType.WRIST_SHOT: 1.0,
            ShotType.SNAP_SHOT: 1.1,
            ShotType.TIP_IN: 0.8,
            ShotType.BACKHAND: 0.9,
            ShotType.WRAPAROUND: 0.7
        }.get(shot_type, 1.0)
        
        # Goalie rebound control
        rebound_control_factor = (20 - goalie.rebound_control) / 20
        
        rebound_chance = base_rebound_chance * type_modifier * rebound_control_factor
        
        return random.random() < rebound_chance

    def _resolve_rebound_chance(self, attacking_team, defending_team):
        """Resolve who gets the rebound and if it results in a goal (legacy compatibility method)."""
        attackers = [p for p in self._get_on_ice(attacking_team) if p.primary_position != PlayerPosition.GOALIE]
        defenders = [p for p in self._get_on_ice(defending_team) if p.primary_position != PlayerPosition.GOALIE]
        
        if not attackers:
            return False
        
        # Find best positioned players
        best_attacker = max(attackers, key=lambda p: p.anticipation + p.offensive_awareness)
        best_defender = max(defenders, key=lambda p: p.anticipation + p.defensive_awareness) if defenders else None
        
        att_roll = best_attacker.anticipation + best_attacker.offensive_awareness + random.randint(1, 10)
        def_roll = (best_defender.anticipation + best_defender.defensive_awareness + random.randint(1, 10)) if best_defender else 0
        
        if att_roll > def_roll:
            # Attacker gets rebound - quick shot attempt
            self.game_stats[best_attacker.id]['rebounds_created'] += 1
            
            # Rebound conversion (~22%, in line with NHL second-chance rates)
            if random.random() < 0.22:
                self.game_stats[best_attacker.id]['rebounds_scored'] += 1
                self._handle_goal(attacking_team, best_attacker, [], ShotType.REBOUND, ShotLocation.CREASE)
                return True
            else:
                goalie = defending_team.get_starting_goalie()
                self._log_event(f"Rebound chance by {best_attacker.full_name}, saved by {goalie.full_name}!", "SAVE")
        
        return False

    def _handle_save(self, goalie, shooter, shot_type, quality):
        """Handle a save event."""
        self._log_event(f"Shot by {shooter.full_name}, saved by {goalie.full_name}!", "SAVE")
        self._emit_pbp("save",
                       goalie=goalie,
                       shooter=shooter,
                       defending_team=getattr(goalie, "team_name", None),
                       shot_type=shot_type.value if hasattr(shot_type, "value") else str(shot_type))

    def _handle_goal(self, scoring_team, shooter, assists, shot_type=None, location=None):
        """Updates score, stats, and log after a goal."""
        shooter.stats.goals += 1
        self.game_stats[shooter.id]['g'] += 1
        
        assist_str = []
        for assist_player in assists:
            assist_player.stats.assists += 1
            self.game_stats[assist_player.id]['a'] += 1
            assist_str.append(assist_player.last_name)
        
        if scoring_team == self.home_team:
            self.home_score += 1
        else:
            self.away_score += 1

        # Positional: puck in the net
        self._ppos_ensure()
        self.puck_pos = [189.0 if scoring_team == self.home_team else 11.0, 42.5]
        self._emit_skate()

        log_msg = f"GOAL for {scoring_team.team_name}! Scored by {shooter.full_name}"
        if shot_type:
            log_msg += f" ({shot_type.value.replace('_', ' ').title()})"
        if assist_str:
            log_msg += f" (Assists: {', '.join(assist_str)})"
        log_msg += f". Score: {self.home_score}-{self.away_score}"
        self._log_event(log_msg, "GOAL")
        
        self._select_starting_lines()
        self._resolve_faceoff()

    def _resolve_faceoff(self):
        """
        Stage 3 Enhancement: Determines faceoff winner with detailed mechanics and zone tracking.
        """
        # Determine faceoff zone based on current zone
        if self.current_zone == Zone.OFFENSIVE_ZONE:
            # If we're in offensive zone, faceoff could be in either offensive or defensive zone of one team
            self.faceoff_zone = random.choice([FaceoffZone.OFFENSIVE_ZONE, FaceoffZone.DEFENSIVE_ZONE])
        elif self.current_zone == Zone.DEFENSIVE_ZONE:
            self.faceoff_zone = random.choice([FaceoffZone.OFFENSIVE_ZONE, FaceoffZone.DEFENSIVE_ZONE])
        else:
            self.faceoff_zone = FaceoffZone.NEUTRAL_ZONE
        
        # Get centers for faceoff
        home_centers = [p for p in self._get_on_ice(self.home_team) if p.primary_position == PlayerPosition.CENTER]
        away_centers = [p for p in self._get_on_ice(self.away_team) if p.primary_position == PlayerPosition.CENTER]
        
        # Fallback to any player if no centers available
        home_player = random.choice(home_centers) if home_centers else random.choice(self._get_on_ice(self.home_team))
        away_player = random.choice(away_centers) if away_centers else random.choice(self._get_on_ice(self.away_team))
        
        # Calculate faceoff skills with situational modifiers
        home_faceoff_skill = self._calculate_faceoff_skill(home_player, self.faceoff_zone, self.home_team)
        away_faceoff_skill = self._calculate_faceoff_skill(away_player, self.faceoff_zone, self.away_team)
        
        # Faceoff battle
        home_roll = home_faceoff_skill + random.randint(-15, 15)
        away_roll = away_faceoff_skill + random.randint(-15, 15)
        
        # Determine outcome
        if home_roll > away_roll + 10:
            outcome = FaceoffOutcome.CLEAN_WIN
            winner = self.home_team
            winner_player = home_player
        elif home_roll > away_roll:
            outcome = FaceoffOutcome.DIRTY_WIN
            winner = self.home_team
            winner_player = home_player
        elif away_roll > home_roll + 10:
            outcome = FaceoffOutcome.CLEAN_WIN
            winner = self.away_team
            winner_player = away_player
        elif away_roll > home_roll:
            outcome = FaceoffOutcome.DIRTY_WIN
            winner = self.away_team
            winner_player = away_player
        else:
            outcome = FaceoffOutcome.BATTLE
            winner = random.choice([self.home_team, self.away_team])
            winner_player = home_player if winner == self.home_team else away_player
        
        # Update faceoff statistics
        self._update_faceoff_stats(home_player, away_player, winner_player, outcome)
        
        # Set zone based on faceoff location and update zone starts
        self._update_zone_starts(winner, self.faceoff_zone)
        
        # Log the faceoff
        zone_desc = self.faceoff_zone.value.replace('_', ' ')
        outcome_desc = outcome.value.replace('_', ' ')
        self._log_event(f"Faceoff in {zone_desc}: {winner_player.full_name} wins ({outcome_desc})", "FACEOFF")
        self._emit_pbp("faceoff",
                       winner_team=winner.team_name,
                       winner_player=winner_player,
                       home_center=home_player,
                       away_center=away_player,
                       zone=self.faceoff_zone.value,
                       outcome=outcome.value)
        self._faceoff_formation(winner, self.faceoff_zone)

        return winner

    def _calculate_faceoff_skill(self, player, faceoff_zone, team):
        """Calculate faceoff skill with zone and situation modifiers."""
        base_skill = player.faceoffs * 2
        
        # Fatigue affects faceoff performance
        fatigue_factor = self.player_fatigue.get(player.id, 100) / 100
        base_skill *= fatigue_factor
        
        # Zone modifiers
        if faceoff_zone == FaceoffZone.OFFENSIVE_ZONE:
            # Offensive zone faceoffs favor attacking mindset
            base_skill += player.offensive_awareness * 0.3
        elif faceoff_zone == FaceoffZone.DEFENSIVE_ZONE:
            # Defensive zone faceoffs favor defensive awareness
            base_skill += player.defensive_awareness * 0.3
        
        # Special situation modifiers
        situation = self._get_current_situation()
        if situation == SpecialSituation.POWER_PLAY and self._is_team_on_power_play(team):
            base_skill += 3  # Slight advantage on power play
        elif situation == SpecialSituation.PENALTY_KILL and self._is_team_on_penalty_kill(team):
            base_skill += 5  # Bigger advantage when shorthanded (more important)
        
        return base_skill

    def _update_faceoff_stats(self, home_player, away_player, winner_player, outcome):
        """Update faceoff statistics for both players."""
        # Update basic faceoff stats
        self.game_stats[home_player.id]['faceoffs_taken'] += 1
        self.game_stats[away_player.id]['faceoffs_taken'] += 1
        
        # Update zone-specific stats
        zone_stat_key = f"faceoffs_{self.faceoff_zone.value}"
        self.game_stats[home_player.id][zone_stat_key] += 1
        self.game_stats[away_player.id][zone_stat_key] += 1
        
        # Update win/loss stats
        if winner_player == home_player:
            self.game_stats[home_player.id]['faceoffs_won'] += 1
            self.game_stats[away_player.id]['faceoffs_lost'] += 1
            self.team_stats[self.home_team.team_name]['faceoffs_won'] += 1
            self.team_stats[self.away_team.team_name]['faceoffs_lost'] += 1
        else:
            self.game_stats[away_player.id]['faceoffs_won'] += 1
            self.game_stats[home_player.id]['faceoffs_lost'] += 1
            self.team_stats[self.away_team.team_name]['faceoffs_won'] += 1
            self.team_stats[self.home_team.team_name]['faceoffs_lost'] += 1

    def _update_zone_starts(self, winning_team, faceoff_zone):
        """Update zone start statistics and set current zone."""
        if faceoff_zone == FaceoffZone.OFFENSIVE_ZONE:
            # Winning team starts in offensive zone
            self.current_zone = Zone.OFFENSIVE_ZONE
            for player in self._get_on_ice(winning_team):
                if player.id in self.game_stats:
                    self.game_stats[player.id]['zone_starts_offensive'] += 1
            
            # Losing team starts in defensive zone
            losing_team = self.away_team if winning_team == self.home_team else self.home_team
            for player in self._get_on_ice(losing_team):
                if player.id in self.game_stats:
                    self.game_stats[player.id]['zone_starts_defensive'] += 1
                    
        elif faceoff_zone == FaceoffZone.DEFENSIVE_ZONE:
            # Winning team starts in defensive zone (their own end)
            self.current_zone = Zone.DEFENSIVE_ZONE
            for player in self._get_on_ice(winning_team):
                if player.id in self.game_stats:
                    self.game_stats[player.id]['zone_starts_defensive'] += 1
            
            # Losing team starts in offensive zone
            losing_team = self.away_team if winning_team == self.home_team else self.home_team
            for player in self._get_on_ice(losing_team):
                if player.id in self.game_stats:
                    self.game_stats[player.id]['zone_starts_offensive'] += 1
        else:
            # Neutral zone start
            self.current_zone = Zone.NEUTRAL_ZONE

    def _get_current_situation(self):
        """
        Stage 3: Determine the current special situation based on penalties.
        """
        home_penalty_count = len(self.home_penalties)
        away_penalty_count = len(self.away_penalties)
        
        home_skaters = 6 - home_penalty_count
        away_skaters = 6 - away_penalty_count
        
        # Ensure minimum of 3 skaters per team
        home_skaters = max(3, home_skaters)
        away_skaters = max(3, away_skaters)
        
        if home_skaters == away_skaters:
            if home_skaters == 6:
                return SpecialSituation.EVEN_STRENGTH
            elif home_skaters == 5:
                return SpecialSituation.FOUR_ON_FOUR
            elif home_skaters == 4:
                return SpecialSituation.THREE_ON_THREE
            else:
                return SpecialSituation.EVEN_STRENGTH  # Fallback
        elif home_skaters > away_skaters:
            if home_skaters == 6 and away_skaters == 5:
                return SpecialSituation.POWER_PLAY  # Home team power play
            elif home_skaters == 6 and away_skaters == 4:
                return SpecialSituation.SIX_ON_FIVE if away_skaters == 4 else SpecialSituation.POWER_PLAY
            elif home_skaters == 5 and away_skaters == 4:
                return SpecialSituation.POWER_PLAY
            elif home_skaters == 5 and away_skaters == 3:
                return SpecialSituation.FOUR_ON_THREE
            else:
                return SpecialSituation.POWER_PLAY
        else:  # away_skaters > home_skaters
            if away_skaters == 6 and home_skaters == 5:
                return SpecialSituation.PENALTY_KILL  # Home team penalty kill
            elif away_skaters == 6 and home_skaters == 4:
                return SpecialSituation.FIVE_ON_SIX if home_skaters == 4 else SpecialSituation.PENALTY_KILL
            elif away_skaters == 5 and home_skaters == 4:
                return SpecialSituation.PENALTY_KILL
            elif away_skaters == 5 and home_skaters == 3:
                return SpecialSituation.THREE_ON_FOUR
            else:
                return SpecialSituation.PENALTY_KILL

    def _select_formation(self, team, situation):
        """
        Stage 3: Select appropriate formation based on situation.
        """
        if situation == SpecialSituation.POWER_PLAY:
            formations = list(PowerPlayFormation)
            return random.choice(formations)
        elif situation == SpecialSituation.PENALTY_KILL:
            formations = list(PenaltyKillFormation)
            return random.choice(formations)
        else:
            return None  # Even strength doesn't use special formations

    def _apply_situation_modifiers(self, base_chance, situation, formation=None):
        """
        Stage 3: Apply modifiers based on special situations.
        """
        modifier = 1.0
        
        if situation == SpecialSituation.POWER_PLAY:
            modifier = 1.3  # 30% boost for power play
            if formation == PowerPlayFormation.UMBRELLA:
                modifier += 0.1  # Extra 10% for umbrella formation
            elif formation == PowerPlayFormation.OVERLOAD:
                modifier += 0.05  # Extra 5% for overload
        elif situation == SpecialSituation.PENALTY_KILL:
            modifier = 0.6  # 40% reduction for penalty kill
            if formation == PenaltyKillFormation.DIAMOND:
                modifier += 0.1  # Better defense with diamond
            elif formation == PenaltyKillFormation.BOX:
                modifier += 0.05  # Slight improvement with box
        elif situation == SpecialSituation.FOUR_ON_FOUR:
            modifier = 1.15  # Slight increase for 4v4 (more open ice)
        elif situation == SpecialSituation.THREE_ON_THREE:
            modifier = 1.25  # Significant increase for 3v3 (very open)
        
        return base_chance * modifier

    def _is_team_on_power_play(self, team):
        """Check if a team is currently on the power play."""
        situation = self._get_current_situation()
        if team == self.home_team:
            return situation == SpecialSituation.POWER_PLAY
        else:
            return situation == SpecialSituation.PENALTY_KILL  # Away team on PP when home on PK

    def _is_team_on_penalty_kill(self, team):
        """Check if a team is currently on the penalty kill."""
        situation = self._get_current_situation()
        if team == self.home_team:
            return situation == SpecialSituation.PENALTY_KILL
        else:
            return situation == SpecialSituation.POWER_PLAY  # Away team on PK when home on PP

    def _select_special_teams_formation(self, team, situation):
        """
        Stage 3: Select appropriate formation based on situation.
        """
        if situation in [SpecialSituation.POWER_PLAY, SpecialSituation.SIX_ON_FIVE, SpecialSituation.FOUR_ON_THREE]:
            # Power play formations
            formations = [PowerPlayFormation.UMBRELLA, PowerPlayFormation.OVERLOAD, 
                         PowerPlayFormation.SPREAD, PowerPlayFormation.CRASH_NET]
            return random.choice(formations)
        elif situation in [SpecialSituation.PENALTY_KILL, SpecialSituation.FIVE_ON_SIX, SpecialSituation.THREE_ON_FOUR]:
            # Penalty kill formations
            formations = [PenaltyKillFormation.BOX, PenaltyKillFormation.DIAMOND,
                         PenaltyKillFormation.TRIANGLE, PenaltyKillFormation.AGGRESSIVE]
            return random.choice(formations)
        else:
            return None

    def _apply_special_situation_modifiers(self, base_chance, situation, team_situation):
        """
        Stage 3: Apply modifiers based on special situations.
        """
        modifier = 1.0
        
        if team_situation == "power_play":
            # Power play increases offensive chances
            if situation == SpecialSituation.POWER_PLAY:
                modifier = 1.8  # 80% increase in scoring chances
            elif situation == SpecialSituation.SIX_ON_FIVE:
                modifier = 2.2  # 120% increase (6 on 5)
            elif situation == SpecialSituation.FOUR_ON_THREE:
                modifier = 2.5  # 150% increase (4 on 3)
                
        elif team_situation == "penalty_kill":
            # Penalty kill decreases offensive chances but increases desperation
            if situation == SpecialSituation.PENALTY_KILL:
                modifier = 0.4  # 60% decrease in scoring chances
            elif situation == SpecialSituation.FIVE_ON_SIX:
                modifier = 0.3  # 70% decrease
            elif situation == SpecialSituation.THREE_ON_FOUR:
                modifier = 0.25  # 75% decrease
            
            # Small chance of short-handed opportunity
            if random.random() < 0.05:  # 5% chance
                modifier = 1.5  # Short-handed breakaway opportunity
                
        elif situation == SpecialSituation.FOUR_ON_FOUR:
            modifier = 1.3  # 30% increase in scoring chances (more open ice)
        elif situation == SpecialSituation.THREE_ON_THREE:
            modifier = 1.6  # 60% increase (very open ice)
        
        return base_chance * modifier

    def _resolve_penalty(self, player, team):
        """
        Stage 3 Enhancement: Enhanced penalty system with special teams tracking.
        """
        penalty_length = random.choice([2, 2, 2, 2, 4, 5])  # Mostly 2min, some 4min, rare 5min
        
        player.stats.penalties_in_minutes += penalty_length
        team_penalties = self.home_penalties if team == self.home_team else self.away_penalties
        opposing_team = self.away_team if team == self.home_team else self.home_team
        
        team_penalties.append({'player': player, 'time': penalty_length * 60})  # Convert to seconds
        
        # Track special teams opportunities
        opposing_team_name = opposing_team.team_name
        self.team_stats[opposing_team_name]['power_play_opportunities'] += 1
        self.team_stats[team.team_name]['penalty_kill_opportunities'] += 1
        
        # Update current situation
        self.current_situation = self._get_current_situation()
        
        # Select formations for special teams
        if self._is_team_on_power_play(opposing_team):
            self.power_play_formation = self._select_special_teams_formation(opposing_team, self.current_situation)
        if self._is_team_on_penalty_kill(team):
            self.penalty_kill_formation = self._select_special_teams_formation(team, self.current_situation)
        
        penalty_desc = f"{penalty_length}-minute penalty"
        self._log_event(f"{penalty_desc} to {player.full_name} ({team.team_name}). {opposing_team.team_name} on power play.", "PENALTY")
        self._emit_pbp("penalty",
                       player=player,
                       team=team.team_name,
                       minutes=penalty_length)

    def _update_penalties(self, time_elapsed):
        """
        Stage 3 Enhancement: Enhanced penalty tracking with special teams time.
        """
        # Track power play and penalty kill time
        current_situation = self._get_current_situation()
        
        if current_situation in [SpecialSituation.POWER_PLAY, SpecialSituation.SIX_ON_FIVE, SpecialSituation.FOUR_ON_THREE]:
            # Home team on power play
            for player in self._get_on_ice(self.home_team):
                if player.id in self.game_stats:
                    self.game_stats[player.id]['power_play_time'] += time_elapsed
            for player in self._get_on_ice(self.away_team):
                if player.id in self.game_stats:
                    self.game_stats[player.id]['penalty_kill_time'] += time_elapsed
                    
        elif current_situation in [SpecialSituation.PENALTY_KILL, SpecialSituation.FIVE_ON_SIX, SpecialSituation.THREE_ON_FOUR]:
            # Away team on power play
            for player in self._get_on_ice(self.away_team):
                if player.id in self.game_stats:
                    self.game_stats[player.id]['power_play_time'] += time_elapsed
            for player in self._get_on_ice(self.home_team):
                if player.id in self.game_stats:
                    self.game_stats[player.id]['penalty_kill_time'] += time_elapsed
        
        # Process penalty time
        for penalty_list in [self.home_penalties, self.away_penalties]:
            for penalty in penalty_list[:]:
                penalty['time'] -= time_elapsed
                if penalty['time'] <= 0:
                    self._log_event(f"{penalty['player'].full_name} is out of the penalty box.", "PENALTY_END")
                    penalty_list.remove(penalty)
        
        # Update situation after penalty changes
        self.current_situation = self._get_current_situation()

    def _handle_goal(self, scoring_team, shooter, assists, shot_type=None, location=None):
        """
        Stage 3 Enhancement: Enhanced goal handling with special teams tracking.
        """
        shooter.stats.goals += 1
        self.game_stats[shooter.id]['g'] += 1
        
        # Check if it's a special teams goal
        current_situation = self._get_current_situation()
        
        if self._is_team_on_power_play(scoring_team):
            # Power play goal
            self.game_stats[shooter.id]['power_play_goals'] += 1
            self.team_stats[scoring_team.team_name]['power_play_goals'] += 1
            
            for assist_player in assists:
                self.game_stats[assist_player.id]['power_play_assists'] += 1
                
        elif self._is_team_on_penalty_kill(scoring_team):
            # Short-handed goal
            self.game_stats[shooter.id]['short_handed_goals'] += 1
            self.team_stats[scoring_team.team_name]['short_handed_goals'] += 1
            
            # Opposing team gets a goal against on their power play
            opposing_team = self.away_team if scoring_team == self.home_team else self.home_team
            self.team_stats[opposing_team.team_name]['penalty_kill_goals_against'] += 1
        
        assist_str = []
        for assist_player in assists:
            assist_player.stats.assists += 1
            self.game_stats[assist_player.id]['a'] += 1
            assist_str.append(assist_player.last_name)
        
        if scoring_team == self.home_team:
            self.home_score += 1
        else:
            self.away_score += 1
            
        log_msg = f"GOAL for {scoring_team.team_name}! Scored by {shooter.full_name}"
        
        # Add special teams context
        if self._is_team_on_power_play(scoring_team):
            log_msg += " (POWER PLAY GOAL)"
        elif self._is_team_on_penalty_kill(scoring_team):
            log_msg += " (SHORT-HANDED GOAL)"
        
        if shot_type:
            log_msg += f" ({shot_type.value.replace('_', ' ').title()})"
        if assist_str:
            log_msg += f" (Assists: {', '.join(assist_str)})"
        log_msg += f". Score: {self.home_score}-{self.away_score}"
        self._log_event(log_msg, "GOAL")
        self._emit_pbp("goal",
                       scoring_team=scoring_team.team_name,
                       shooter=shooter,
                       assists=list(assists),
                       shot_type=shot_type.value if shot_type is not None and hasattr(shot_type, "value") else None,
                       location=location.value if location is not None and hasattr(location, "value") else None,
                       home_score=self.home_score,
                       away_score=self.away_score)
        
        # End power play on power play goal (most common rule)
        if self._is_team_on_power_play(scoring_team):
            opposing_team = self.away_team if scoring_team == self.home_team else self.home_team
            opposing_penalties = self.away_penalties if scoring_team == self.home_team else self.home_penalties
            
            if opposing_penalties:
                # Remove the first penalty (oldest)
                expired_penalty = opposing_penalties.pop(0)
                self._log_event(f"Power play ends - {expired_penalty['player'].full_name} released from penalty box.", "PENALTY_END")
        
        self._select_starting_lines()
        self._resolve_faceoff()

    def _update_shot_stats(self, shooter, attacking_team, defending_team, quality, distance, shot_type):
        """
        Stage 3 Enhancement: Enhanced shot stats with special teams tracking.
        """
        # Basic shot stats (Stage 1)
        self.game_stats[shooter.id]['shots_on_goal'] += 1
        self.game_stats[shooter.id]['shot_attempts'] += 1
        self.game_stats[shooter.id]['shot_distance_total'] += distance
        
        # Quality tracking (Stage 1)
        quality_key = f"{quality}_danger_shots"
        self.game_stats[shooter.id][quality_key] += 1
        
        # Special teams shot tracking (Stage 3)
        if self._is_team_on_power_play(attacking_team):
            self.game_stats[shooter.id]['power_play_shots'] += 1
            self.team_stats[attacking_team.team_name]['power_play_shots'] += 1
            
            # Track shots against for penalty kill
            defending_team_name = defending_team.team_name
            self.team_stats[defending_team_name]['penalty_kill_shots_against'] += 1
        
        # Team stats (Stage 1)
        att_team_name = attacking_team.team_name
        def_team_name = defending_team.team_name
        
        self.team_stats[att_team_name]['shots_on_goal'] += 1
        self.team_stats[att_team_name]['shot_attempts'] += 1
        
        if quality == "high":
            self.team_stats[att_team_name]['high_danger_chances'] += 1
        
        # Corsi tracking (Stage 1)
        self.game_stats[shooter.id]['corsi_for'] += 1
        for player in self._get_on_ice(defending_team):
            if player.id in self.game_stats:
                self.game_stats[player.id]['corsi_against'] += 1
        
        self.team_stats[att_team_name]['corsi_for'] += 1
        self.team_stats[def_team_name]['corsi_against'] += 1

    def _resolve_offensive_zone_play(self, attacking_team, defending_team):
        """
        Stage 3 Enhancement: Enhanced offensive zone play with special situations.
        """
        attacking_skaters = [p for p in self._get_on_ice(attacking_team) if p.primary_position != PlayerPosition.GOALIE]
        defending_skaters = [p for p in self._get_on_ice(defending_team) if p.primary_position != PlayerPosition.GOALIE]
        
        if not attacking_skaters:
            return self._zone_clear(defending_team)
        
        # Update zone time stats (Stage 2)
        self._update_zone_time_stats(attacking_team, defending_team)
        
        # Get current special situation and formation (Stage 3)
        current_situation = self._get_current_situation()
        formation = self._select_formation(attacking_team, current_situation)
        
        # Base event probabilities
        shot_chance = 0.3
        turnover_chance = 0.2
        cycle_chance = 0.2
        maintain_chance = 0.3
        
        # Apply special situation modifiers (Stage 3)
        shot_chance = self._apply_situation_modifiers(shot_chance, current_situation, formation)
        
        # Track formation usage
        if formation:
            if not hasattr(self, 'formation_usage'):
                self.formation_usage = {'power_play': {}, 'penalty_kill': {}}
            
            if current_situation == SpecialSituation.POWER_PLAY:
                self.formation_usage['power_play'][formation] = self.formation_usage['power_play'].get(formation, 0) + 1
            elif current_situation == SpecialSituation.PENALTY_KILL:
                self.formation_usage['penalty_kill'][formation] = self.formation_usage['penalty_kill'].get(formation, 0) + 1
        
        # Random events in offensive zone
        event_roll = random.random()
        
        if event_roll < shot_chance:
            shooter = self._weighted_skater_choice(attacking_skaters, "shoot")
            self._resolve_scoring_chance(shooter, attacking_team, defending_team)
        elif event_roll < shot_chance + turnover_chance:
            return self._attempt_zone_clear(defending_team, attacking_team)
        elif event_roll < shot_chance + turnover_chance + cycle_chance:
            return self._resolve_offensive_cycle(attacking_team, defending_team)
        else:
            return self._maintain_offensive_possession(attacking_team)

    def _handle_overtime(self):
        """Simulates overtime.

        Regular season: 5-minute 3-on-3 sudden death, then shootout.
        Playoffs: 20-minute 5-on-5 sudden-death periods until someone scores.
        """
        # Sudden-death bookkeeping consumed by _simulate_period
        self._ot_sudden_death = True
        try:
            if self.is_playoff:
                ot_num = 1
                while self.home_score == self.away_score:
                    label = f"OT{ot_num}" if ot_num > 1 else "OT"
                    self._log_event(
                        f"End of {'regulation' if ot_num == 1 else 'overtime'}, game is tied. "
                        f"Starting {label} (20-min 5-on-5 sudden death)!",
                        "PERIOD_START",
                    )
                    self.period = 3 + ot_num
                    self.clock = 1200  # 20 minutes, 5-on-5
                    self._period_length = 1200
                    self._ot_start_score = (self.home_score, self.away_score)
                    self._simulate_period()
                    ot_num += 1
                    # Marathon guard: should essentially never trigger (sudden death
                    # always ends on a goal), but prevents an infinite loop if
                    # scoring somehow stalls. NO shootout in playoffs — resolve
                    # with a strength-weighted golden goal instead.
                    if ot_num > 10:
                        self._log_event(
                            f"Marathon game! {ot_num - 1} scoreless OT periods — "
                            "going to a golden-goal resolution.",
                            "PERIOD_START",
                        )
                        self._resolve_marathon_golden_goal()
                        break
            else:
                self._log_event("End of regulation, game is tied. Starting Overtime!", "PERIOD_START")
                self.period = 4
                self.clock = 300  # 5-minute 3-on-3
                self._period_length = 300
                self._ot_start_score = (self.home_score, self.away_score)
                self._simulate_period()
        finally:
            self._ot_sudden_death = False
            self._ot_start_score = None

    def _resolve_marathon_golden_goal(self):
        """Resolve a marathon playoff OT (10+ scoreless periods) with a
        strength-weighted golden goal. Playoffs never use shootouts."""
        def ot_strength(team):
            skaters = [p for p in team.roster
                       if p.primary_position != PlayerPosition.GOALIE][:18]
            if not skaters:
                return 75.0
            return sum((p.shooting_accuracy + p.offensive_awareness + p.skating) / 3
                       for p in skaters) / len(skaters)

        home_s = ot_strength(self.home_team)
        away_s = ot_strength(self.away_team)
        home_prob = home_s / (home_s + away_s)
        winner = self.home_team if random.random() < home_prob else self.away_team
        candidates = [p for p in self._get_on_ice(winner)
                      if p.primary_position != PlayerPosition.GOALIE]
        if not candidates:
            candidates = [p for p in winner.roster
                          if p.primary_position != PlayerPosition.GOALIE]
        scorer = max(candidates,
                     key=lambda p: p.shooting_accuracy + p.offensive_awareness)
        self._handle_goal(winner, scorer, [], ShotType.WRIST_SHOT,
                          ShotLocation.HIGH_SLOT)
        self._log_event(
            f"GOLDEN GOAL in marathon OT! {scorer.full_name} wins it for "
            f"{winner.team_name}. Final: {self.home_score}-{self.away_score}",
            "GOAL",
        )

    def _handle_shootout(self):
        """Simulates a 3-round shootout if the game is still tied."""
        self._log_event("Overtime ends, still tied. Heading to a shootout!", "SHOOTOUT_START")
        self._emit_pbp("shootout_start")
        home_shooters = random.sample([p for p in self.home_team.roster if p.primary_position != PlayerPosition.GOALIE], 3)
        away_shooters = random.sample([p for p in self.away_team.roster if p.primary_position != PlayerPosition.GOALIE], 3)

        for i in range(3):
            if self._resolve_shootout_attempt(away_shooters[i], self.home_team.get_starting_goalie()):
                self.away_score += 1
            if self._resolve_shootout_attempt(home_shooters[i], self.away_team.get_starting_goalie()):
                self.home_score += 1
        
        while self.home_score == self.away_score:
            home_shooter = random.choice([p for p in self.home_team.roster if p not in home_shooters and p.primary_position != PlayerPosition.GOALIE])
            away_shooter = random.choice([p for p in self.away_team.roster if p not in away_shooters and p.primary_position != PlayerPosition.GOALIE])
            if self._resolve_shootout_attempt(away_shooter, self.home_team.get_starting_goalie()): self.away_score += 1
            if self._resolve_shootout_attempt(home_shooter, self.away_team.get_starting_goalie()): self.home_score += 1

        self._emit_pbp("shootout_end",
                       winner=self.home_team.team_name if self.home_score > self.away_score else self.away_team.team_name,
                       home_score=self.home_score, away_score=self.away_score)

    def _resolve_shootout_attempt(self, shooter, goalie):
        """Resolves a single shootout attempt."""
        shot_roll = shooter.shooting + shooter.deking + random.randint(1, 20)
        save_roll = goalie.goaltending * 2.5 + random.randint(1, 20)
        is_goal = shot_roll > save_roll
        result = "scores" if is_goal else "is stopped"
        self._log_event(f"Shootout: {shooter.full_name} {result} against {goalie.full_name}!", "SHOOTOUT_ATTEMPT")
        self._emit_pbp("shootout_attempt", shooter=shooter, goalie=goalie,
                       scored=is_goal,
                       shooting_team=getattr(shooter, "team_name", None))
        return is_goal
        
    def _check_for_notable_performances(self):
        """Checks for hat-tricks, shutouts, etc., and adds them to the log."""
        for player_id, stats in self.game_stats.items():
            if stats['g'] >= 3:
                self.notable_events.append({'player': stats['player'], 'event': 'records a hat-trick'})
        
        if self.home_score == 0:
            goalie = self.away_team.get_starting_goalie()
            self.notable_events.append({'player': goalie, 'event': 'earns a shutout'})
        if self.away_score == 0:
            goalie = self.home_team.get_starting_goalie()
            self.notable_events.append({'player': goalie, 'event': 'earns a shutout'})

    def _lineup_player(self, team, flat_key):
        """Read one lineup slot, flat F1_LW-style key first, nested fallback.

        Editors historically wrote nested {'Forwards': [[LW,C,RW]x4],
        'Defense': [[L,R]xN]} while the sim reads flat keys; this keeps both
        working so user lines always reach the ice.
        """
        lineup = getattr(team, 'lineup', None) or {}
        player = lineup.get(flat_key)
        if player:
            return player
        try:
            parts = flat_key.split('_')
            if len(parts) != 2:
                return None
            slot, pos = parts
            if slot.startswith('F'):
                line = (lineup.get('Forwards') or [])[int(slot[1:]) - 1]
                return line[{'LW': 0, 'C': 1, 'RW': 2}[pos]] if line else None
            if slot.startswith('D'):
                pair = (lineup.get('Defense') or [])[int(slot[1:]) - 1]
                return pair[{'L': 0, 'R': 1}[pos]] if pair else None
        except (IndexError, KeyError, ValueError, TypeError):
            return None
        return None

    def _get_on_ice(self, team):
        """Returns the list of players currently on the ice for a team, based on lines."""
        num_skaters = 5
        if self.period == 4: # 3-on-3 OT
            num_skaters = 3
        
        penalized_players = [p['player'] for p in (self.home_penalties if team == self.home_team else self.away_penalties)]
        
        # Simple line rotation logic
        current_line = (self.clock // 45) % 4 + 1 # Change lines every 45 seconds
        current_d_pair = (self.clock // 60) % 3 + 1

        # Line matching: aggressive home-ice deployment reacts to score state
        if team == self.home_team and getattr(team, 'tactic_line_matching', 'Standard') == 'Aggressive':
            goal_diff = self.home_score - self.away_score
            rotation = (self.clock // 45) % 2
            if goal_diff <= -2:
                current_line = 1 if rotation == 0 else 2  # chase the game: top six
            elif goal_diff >= 2:
                current_line = 3 if rotation == 0 else 4  # protect the lead: bottom six

        on_ice = []
        
        # Get forwards from the current line
        for pos in ['LW', 'C', 'RW']:
            pos_enum = None
            if pos == 'LW':
                pos_enum = PlayerPosition.LEFT_WING
            elif pos == 'C':
                pos_enum = PlayerPosition.CENTER
            elif pos == 'RW':
                pos_enum = PlayerPosition.RIGHT_WING
                
            player = self._lineup_player(team, f"F{current_line}_{pos}")
            if player and player not in penalized_players:
                on_ice.append(player)

        # Get defensemen from the current pairing
        for pos in ['L', 'R']:
            pos_enum = None
            if pos == 'L':
                pos_enum = PlayerPosition.LEFT_DEFENSE
            elif pos == 'R':
                pos_enum = PlayerPosition.RIGHT_DEFENSE
                
            player = self._lineup_player(team, f"D{current_d_pair}_{pos}")
            if player and player not in penalized_players:
                on_ice.append(player)
        
        # If lineup is incomplete, fill with best available players
        if len(on_ice) < num_skaters:
            best_available = sorted([p for p in team.roster if p not in on_ice and p not in penalized_players], key=lambda p: p.overall_rating(), reverse=True)
            on_ice.extend(best_available[:num_skaters - len(on_ice)])

        on_ice.append(team.get_starting_goalie())
        return on_ice

    def _select_starting_lines(self):
        """Selects the players to start a shift."""
        self.home_on_ice = self._get_on_ice(self.home_team)
        self.away_on_ice = self._get_on_ice(self.away_team)

    def _emit_pbp(self, event_type, **payload):
        """Emit a play-by-play event to registered listeners (no-op if none)."""
        if not self.pbp_listeners:
            return
        try:
            clock = max(0, self.clock)
            elapsed = max(0, self._period_length - clock)
        except Exception:
            clock, elapsed = 0, 0
        ev = {
            "type": event_type,
            "period": getattr(self, "period", 1),
            "clock": clock,               # seconds remaining in period (clamped)
            "elapsed": elapsed,            # seconds elapsed in period
            "t": (max(1, getattr(self, "period", 1)) - 1) * 1200 + elapsed,
            "home_score": getattr(self, "home_score", 0),
            "away_score": getattr(self, "away_score", 0),
        }
        ev.update(payload)
        for cb in list(self.pbp_listeners):
            try:
                cb(ev)
            except Exception:
                pass

    @staticmethod
    def _pbp_num(value):
        """Best-effort numeric coercion for PBP payloads (quality may be an enum/str)."""
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            return str(value) if value is not None else None

    def _log_event(self, message, event_type="INFO"):
        """Adds an event to the game log with a timestamp."""
        minutes = self.clock // 60
        seconds = self.clock % 60
        timestamp = f"P{self.period} - {minutes:02d}:{seconds:02d}"
        self.game_log.append(f"[{timestamp}] [{event_type}] {message}")

    def get_advanced_team_stats(self, team_name):
        """Get advanced statistics for a team from this game (Stages 1, 2, 3 & 4)."""
        stats = self.team_stats.get(team_name, {})
        
        # Stage 1: Calculate derived stats
        corsi_for = stats.get('corsi_for', 0)
        corsi_against = stats.get('corsi_against', 0)
        corsi_total = corsi_for + corsi_against
        
        corsi_percentage = (corsi_for / corsi_total * 100) if corsi_total > 0 else 0
        
        shots_on_goal = stats.get('shots_on_goal', 0)
        shooting_percentage = (self._get_team_goals(team_name) / shots_on_goal * 100) if shots_on_goal > 0 else 0
        
        # Stage 2: Zone and possession stats
        zone_time_off = stats.get('zone_time_offensive', 0)
        zone_time_def = stats.get('zone_time_defensive', 0)
        total_zone_time = zone_time_off + zone_time_def
        
        zone_time_percentage = (zone_time_off / total_zone_time * 100) if total_zone_time > 0 else 0
        
        zone_entries = stats.get('zone_entries', 0)
        controlled_entries = stats.get('controlled_entries', 0)
        controlled_entry_percentage = (controlled_entries / zone_entries * 100) if zone_entries > 0 else 0
        
        # Stage 3: Special teams stats
        faceoffs_won = stats.get('faceoffs_won', 0)
        faceoffs_lost = stats.get('faceoffs_lost', 0)
        total_faceoffs = faceoffs_won + faceoffs_lost
        faceoff_win_percentage = (faceoffs_won / total_faceoffs * 100) if total_faceoffs > 0 else 0
        
        pp_opportunities = stats.get('power_play_opportunities', 0)
        pp_goals = stats.get('power_play_goals', 0)
        power_play_percentage = (pp_goals / pp_opportunities * 100) if pp_opportunities > 0 else 0
        
        pk_opportunities = stats.get('penalty_kill_opportunities', 0)
        pk_goals_against = stats.get('penalty_kill_goals_against', 0)
        penalty_kill_percentage = ((pk_opportunities - pk_goals_against) / pk_opportunities * 100) if pk_opportunities > 0 else 0
        
        return {
            # Stage 1 stats
            'shots_on_goal': shots_on_goal,
            'shot_attempts': stats.get('shot_attempts', 0),
            'blocked_shots': stats.get('blocked_shots', 0),
            'shots_blocked': stats.get('shots_blocked', 0),
            'high_danger_chances': stats.get('high_danger_chances', 0),
            'corsi_for': corsi_for,
            'corsi_against': corsi_against,
            'corsi_percentage': round(corsi_percentage, 1),
            'shooting_percentage': round(shooting_percentage, 1),
            # Stage 2 stats
            'zone_time_offensive': round(zone_time_off, 1),
            'zone_time_defensive': round(zone_time_def, 1),
            'zone_time_percentage': round(zone_time_percentage, 1),
            'zone_entries': zone_entries,
            'zone_exits': stats.get('zone_exits', 0),
            'controlled_entries': controlled_entries,
            'controlled_entry_percentage': round(controlled_entry_percentage, 1),
            'dump_ins': stats.get('dump_ins', 0),
            'possession_time': round(stats.get('possession_time', 0), 1),
            'puck_battles_won': stats.get('puck_battles_won', 0),
            'puck_battles_lost': stats.get('puck_battles_lost', 0),
            # Stage 3 stats
            'faceoffs_won': faceoffs_won,
            'faceoffs_lost': faceoffs_lost,
            'faceoff_win_percentage': round(faceoff_win_percentage, 1),
            'power_play_opportunities': pp_opportunities,
            'power_play_goals': pp_goals,
            'power_play_percentage': round(power_play_percentage, 1),
            'penalty_kill_opportunities': pk_opportunities,
            'penalty_kill_goals_against': pk_goals_against,
            'penalty_kill_percentage': round(penalty_kill_percentage, 1),
            'short_handed_goals': stats.get('short_handed_goals', 0),
            'power_play_shots': stats.get('power_play_shots', 0),
            'penalty_kill_shots_against': stats.get('penalty_kill_shots_against', 0),
            # Stage 4 stats
            'hits': stats.get('hits', 0),
            'hits_against': stats.get('hits_against', 0),
            'takeaways': stats.get('takeaways', 0),
            'giveaways': stats.get('giveaways', 0),
            'turnovers_forced': stats.get('turnovers_forced', 0),
            'turnovers_committed': stats.get('turnovers_committed', 0),
            'blocked_shots_by_team': stats.get('blocked_shots_by_team', 0),
            'shots_blocked_against_team': stats.get('shots_blocked_against_team', 0),
            'checking_effectiveness': round((stats.get('hits', 0) / max(stats.get('hits', 0) + stats.get('takeaways', 0), 1) * 100), 1),
            'physical_penalties': stats.get('physical_penalties', 0),
            'defensive_zone_time': round(stats.get('defensive_zone_time', 0), 1)
        }

    def get_advanced_player_stats(self, player_id):
        """Get advanced statistics for a player from this game (Stages 1, 2, 3 & 4)."""
        stats = self.game_stats.get(player_id, {})
        
        # Stage 1: Basic calculations
        shots_on_goal = stats.get('shots_on_goal', 0)
        shot_attempts = stats.get('shot_attempts', 0)
        
        shooting_percentage = (stats.get('g', 0) / shots_on_goal * 100) if shots_on_goal > 0 else 0
        avg_shot_distance = (stats.get('shot_distance_total', 0) / shots_on_goal) if shots_on_goal > 0 else 0
        
        corsi_for = stats.get('corsi_for', 0)
        corsi_against = stats.get('corsi_against', 0)
        corsi_total = corsi_for + corsi_against
        corsi_percentage = (corsi_for / corsi_total * 100) if corsi_total > 0 else 0
        
        # Stage 2: Zone and possession calculations
        zone_entries = stats.get('zone_entries', 0)
        controlled_entries = stats.get('controlled_zone_entries', 0)
        controlled_entry_rate = (controlled_entries / zone_entries * 100) if zone_entries > 0 else 0
        
        puck_battles_won = stats.get('puck_battles_won', 0)
        puck_battles_lost = stats.get('puck_battles_lost', 0)
        puck_battle_total = puck_battles_won + puck_battles_lost
        puck_battle_win_rate = (puck_battles_won / puck_battle_total * 100) if puck_battle_total > 0 else 0
        
        # Stage 3: Faceoff and special teams calculations
        faceoffs_taken = stats.get('faceoffs_taken', 0)
        faceoffs_won = stats.get('faceoffs_won', 0)
        faceoff_win_percentage = (faceoffs_won / faceoffs_taken * 100) if faceoffs_taken > 0 else 0
        
        pp_goals = stats.get('power_play_goals', 0)
        pp_assists = stats.get('power_play_assists', 0)
        pp_points = pp_goals + pp_assists
        
        return {
            # Stage 1 stats
            'goals': stats.get('g', 0),
            'assists': stats.get('a', 0),
            'shots_on_goal': shots_on_goal,
            'shot_attempts': shot_attempts,
            'blocked_shots': stats.get('blocked_shots', 0),
            'missed_shots': stats.get('missed_shots', 0),
            'shots_blocked': stats.get('shots_blocked', 0),
            'high_danger_shots': stats.get('high_danger_shots', 0),
            'medium_danger_shots': stats.get('medium_danger_shots', 0),
            'low_danger_shots': stats.get('low_danger_shots', 0),
            'rebounds_created': stats.get('rebounds_created', 0),
            'rebounds_scored': stats.get('rebounds_scored', 0),
            'corsi_for': corsi_for,
            'corsi_against': corsi_against,
            'corsi_percentage': round(corsi_percentage, 1),
            'shooting_percentage': round(shooting_percentage, 1),
            'avg_shot_distance': round(avg_shot_distance, 1),
            # Stage 2 stats
            'zone_entries': zone_entries,
            'zone_exits': stats.get('zone_exits', 0),
            'controlled_zone_entries': controlled_entries,
            'controlled_entry_rate': round(controlled_entry_rate, 1),
            'dump_ins': stats.get('dump_ins', 0),
            'zone_time_offensive': round(stats.get('zone_time_offensive', 0), 1),
            'zone_time_defensive': round(stats.get('zone_time_defensive', 0), 1),
            'zone_starts_offensive': stats.get('zone_starts_offensive', 0),
            'zone_starts_defensive': stats.get('zone_starts_defensive', 0),
            'possession_time': round(stats.get('possession_time', 0), 1),
            'possession_gains': stats.get('possession_gains', 0),
            'possession_losses': stats.get('possession_losses', 0),
            'puck_battles_won': puck_battles_won,
            'puck_battles_lost': puck_battles_lost,
            'puck_battle_win_rate': round(puck_battle_win_rate, 1),
            # Stage 3 stats
            'faceoffs_taken': faceoffs_taken,
            'faceoffs_won': faceoffs_won,
            'faceoffs_lost': stats.get('faceoffs_lost', 0),
            'faceoff_win_percentage': round(faceoff_win_percentage, 1),
            'faceoffs_neutral_zone': stats.get('faceoffs_neutral_zone', 0),
            'faceoffs_offensive_zone': stats.get('faceoffs_offensive_zone', 0),
            'faceoffs_defensive_zone': stats.get('faceoffs_defensive_zone', 0),
            'power_play_goals': pp_goals,
            'power_play_assists': pp_assists,
            'power_play_points': pp_points,
            'power_play_shots': stats.get('power_play_shots', 0),
            'penalty_kill_goals': stats.get('penalty_kill_goals', 0),
            'penalty_kill_assists': stats.get('penalty_kill_assists', 0),
            'short_handed_goals': stats.get('short_handed_goals', 0),
            'power_play_time': round(stats.get('power_play_time', 0) / 60, 1),  # Convert to minutes
            'penalty_kill_time': round(stats.get('penalty_kill_time', 0) / 60, 1),  # Convert to minutes
            # Stage 4 stats
            'hits': stats.get('hits', 0),
            'hits_taken': stats.get('hits_taken', 0),
            'takeaways': stats.get('takeaways', 0),
            'giveaways': stats.get('giveaways', 0),
            'blocked_shots_by': stats.get('blocked_shots_by', 0),
            'shots_blocked_against': stats.get('shots_blocked_against', 0),
            'checks': stats.get('checks', 0),
            'defensive_plays': stats.get('defensive_plays', 0),
            'turnovers_forced': stats.get('turnovers_forced', 0),
            'turnovers_committed': stats.get('turnovers_committed', 0),
            'physical_penalties': stats.get('physical_penalties', 0),
            'plus_minus_physical': stats.get('hits', 0) - stats.get('hits_taken', 0),
            'takeaway_giveaway_ratio': round(stats.get('takeaways', 0) / max(stats.get('giveaways', 1), 1), 2)
        }

    def _get_team_goals(self, team_name):
        """Helper to get total goals for a team."""
        if team_name == self.home_team.team_name:
            return self.home_score
        elif team_name == self.away_team.team_name:
            return self.away_score
        return 0

    def get_state(self, step):
        """
        Returns a dict with player positions, puck position, and events for the given step.
        This is a stub for integration with GAME_VIEWER.
        """
        # For now, just return dummy positions and events based on current score and period
        # You can expand this to track actual positions and puck movement if desired
        home_players = [
            {'x': 20 + step % 60, 'y': 20, 'number': p.jersey_number, 'team': 'home'}
            for p in self.home_team.roster[:6]
        ]
        away_players = [
            {'x': 80 - step % 60, 'y': 30, 'number': p.jersey_number, 'team': 'away'}
            for p in self.away_team.roster[:6]
        ]
        puck = {'x': 50 + (step % 20), 'y': 25}
        # Show a goal event if score changes
        events = []
        if step == 50:
            events.append(f"Goal by {self.home_team.roster[0].full_name}!")
        if step == 100:
            events.append(f"Penalty to {self.away_team.roster[0].full_name}")
        if step == 150:
            events.append(f"Shot by {self.home_team.roster[1].full_name}")
        return {
            'players': home_players + away_players,
            'puck': puck,
            'events': events
        }

    # ===== STAGE 4: PHYSICAL PLAY & DEFENSIVE SYSTEMS =====
    
    def _attempt_hit(self, hitting_player, target_player, hit_type=HitType.BODY_CHECK):
        """
        Stage 4: Simulate a hitting attempt with detailed mechanics.
        """
        # Base success rate depends on player attributes
        hit_skill = (hitting_player.checking + hitting_player.aggressiveness + hitting_player.determination) / 3
        target_avoidance = (target_player.speed + target_player.agility + target_player.anticipation) / 3
        
        # Hit type modifiers
        type_modifier = {
            HitType.BODY_CHECK: 1.0,
            HitType.POKE_CHECK: 1.2,
            HitType.STICK_CHECK: 1.1,
            HitType.BOARD_CHECK: 0.9,
            HitType.CLEAN_HIT: 0.8,
            HitType.CHARGING: 0.7,
            HitType.BOARDING: 0.6
        }.get(hit_type, 1.0)
        
        # Calculate success probability
        base_success = (hit_skill / (hit_skill + target_avoidance)) * type_modifier
        success_chance = max(0.1, min(0.9, base_success))
        
        # Physical intensity affects hit frequency
        success_chance *= self.physical_intensity
        
        hit_successful = random.random() < success_chance
        
        if hit_successful:
            result = self._resolve_hit_result(hitting_player, target_player, hit_type)
            self._record_hit_stats(hitting_player, target_player, hit_type, result)
            return result
        else:
            self._record_hit_stats(hitting_player, target_player, hit_type, HitResult.MISSED)
            return HitResult.MISSED

    def _resolve_hit_result(self, hitting_player, target_player, hit_type):
        """
        Stage 4: Determine the outcome of a successful hit.
        """
        # Base result probabilities
        results = [
            (HitResult.SUCCESSFUL, 0.6),
            (HitResult.TURNOVER_CAUSED, 0.25),
            (HitResult.PENALTY_DRAWN, 0.1),
            (HitResult.INJURY_CAUSED, 0.05)
        ]
        
        # Adjust probabilities based on hit type
        if hit_type in [HitType.CHARGING, HitType.BOARDING]:
            # Dirty hits more likely to cause penalties/injuries
            results = [
                (HitResult.SUCCESSFUL, 0.3),
                (HitResult.TURNOVER_CAUSED, 0.2),
                (HitResult.PENALTY_DRAWN, 0.4),
                (HitResult.INJURY_CAUSED, 0.1)
            ]
        elif hit_type in [HitType.POKE_CHECK, HitType.STICK_CHECK]:
            # Skill-based hits more likely to cause turnovers
            results = [
                (HitResult.SUCCESSFUL, 0.4),
                (HitResult.TURNOVER_CAUSED, 0.5),
                (HitResult.PENALTY_DRAWN, 0.05),
                (HitResult.INJURY_CAUSED, 0.05)
            ]
        
        # Select result based on probabilities
        rand = random.random()
        cumulative = 0
        for result, prob in results:
            cumulative += prob
            if rand < cumulative:
                return result
        
        return HitResult.SUCCESSFUL

    def _record_hit_stats(self, hitting_player, target_player, hit_type, result):
        """
        Stage 4: Record hitting statistics and update tracking.
        """
        hitting_team = self._get_player_team(hitting_player)
        target_team = self._get_player_team(target_player)
        
        # Update individual stats
        if hitting_player.id in self.game_stats:
            self.game_stats[hitting_player.id]['hits'] += 1
            if hit_type in [HitType.CHARGING, HitType.BOARDING] and result == HitResult.PENALTY_DRAWN:
                self.game_stats[hitting_player.id]['physical_penalties'] += 1
        
        if target_player.id in self.game_stats:
            self.game_stats[target_player.id]['hits_taken'] += 1
        
        # Update team stats
        hitting_team_name = hitting_team.team_name
        target_team_name = target_team.team_name
        
        if hitting_team_name in self.team_stats:
            self.team_stats[hitting_team_name]['hits'] += 1
            if result == HitResult.PENALTY_DRAWN:
                self.team_stats[hitting_team_name]['physical_penalties'] += 1
        
        if target_team_name in self.team_stats:
            self.team_stats[target_team_name]['hits_against'] += 1
        
        # Update global tracking
        if result == HitResult.SUCCESSFUL:
            self.hit_tracking['successful_hits'] += 1
        elif result == HitResult.MISSED:
            self.hit_tracking['missed_hits'] += 1
        elif result == HitResult.PENALTY_DRAWN:
            self.hit_tracking['penalties_from_hits'] += 1
        
        # Log significant hits
        if result in [HitResult.TURNOVER_CAUSED, HitResult.PENALTY_DRAWN, HitResult.INJURY_CAUSED]:
            self._log_event(f"{hit_type.value.title()} by {hitting_player.full_name} on {target_player.full_name} - {result.value}", "HIT")
            self._emit_pbp("hit",
                           hitting_player=hitting_player,
                           target_player=target_player,
                           hit_type=hit_type.value,
                           result=result.value)

    def _resolve_turnover(self, player_losing_puck, player_gaining_puck, turnover_type):
        """
        Stage 4: Handle detailed turnover tracking and resolution.
        """
        losing_team = self._get_player_team(player_losing_puck)
        gaining_team = self._get_player_team(player_gaining_puck)
        
        # Record turnover stats
        if player_losing_puck.id in self.game_stats:
            if turnover_type in [TurnoverType.GIVEAWAY, TurnoverType.UNFORCED_ERROR]:
                self.game_stats[player_losing_puck.id]['giveaways'] += 1
                self.game_stats[player_losing_puck.id]['turnovers_committed'] += 1
        
        if player_gaining_puck.id in self.game_stats:
            if turnover_type in [TurnoverType.TAKEAWAY, TurnoverType.FORCED_ERROR, TurnoverType.STRIP, TurnoverType.INTERCEPTION]:
                self.game_stats[player_gaining_puck.id]['takeaways'] += 1
                self.game_stats[player_gaining_puck.id]['turnovers_forced'] += 1
                self.game_stats[player_gaining_puck.id]['defensive_plays'] += 1
        
        # Update team stats
        losing_team_name = losing_team.team_name
        gaining_team_name = gaining_team.team_name
        
        if losing_team_name in self.team_stats:
            if turnover_type in [TurnoverType.GIVEAWAY, TurnoverType.UNFORCED_ERROR]:
                self.team_stats[losing_team_name]['giveaways'] += 1
                self.team_stats[losing_team_name]['turnovers_committed'] += 1
        
        if gaining_team_name in self.team_stats:
            if turnover_type in [TurnoverType.TAKEAWAY, TurnoverType.FORCED_ERROR, TurnoverType.STRIP, TurnoverType.INTERCEPTION]:
                self.team_stats[gaining_team_name]['takeaways'] += 1
                self.team_stats[gaining_team_name]['turnovers_forced'] += 1
        
        # Change possession
        self.possession_team = gaining_team
        self.possession_player = player_gaining_puck

        # Positional: puck jumps to the thief, teams transition
        self._ppos_ensure()
        self.puck_pos = self._ppos_get(player_gaining_puck)[:]
        self._shape_positions(gaining_team, self.puck_pos)
        self._emit_skate()

        # Log event
        self._log_event(f"{turnover_type.value.title()}: {player_gaining_puck.full_name} strips puck from {player_losing_puck.full_name}", "TURNOVER")

        return gaining_team

    def _attempt_defensive_play(self, defending_player, attacking_player, action_type):
        """
        Stage 4: Simulate defensive actions like stick lifts, interceptions, etc.
        """
        # Base success rate depends on defensive attributes
        defensive_skill = (defending_player.checking + defending_player.anticipation + defending_player.positioning) / 3
        offensive_skill = (attacking_player.puck_handling + attacking_player.vision + attacking_player.composure) / 3
        
        # Action type modifiers
        action_modifier = {
            DefensiveAction.STICK_LIFT: 1.1,
            DefensiveAction.BODY_POSITION: 1.0,
            DefensiveAction.ACTIVE_STICK: 1.2,
            DefensiveAction.SHOT_BLOCK: 0.8,
            DefensiveAction.PASS_INTERCEPTION: 0.9,
            DefensiveAction.FORECHECKING: 1.0,
            DefensiveAction.BACKCHECKING: 0.9
        }.get(action_type, 1.0)
        
        # Defensive pressure affects success
        success_rate = (defensive_skill / (defensive_skill + offensive_skill)) * action_modifier * self.defensive_pressure
        success_rate = max(0.1, min(0.8, success_rate))
        
        if random.random() < success_rate:
            self._record_defensive_success(defending_player, action_type)
            return True
        else:
            return False

    def _record_defensive_success(self, defending_player, action_type):
        """
        Stage 4: Record successful defensive plays.
        """
        if defending_player.id in self.game_stats:
            self.game_stats[defending_player.id]['defensive_plays'] += 1
            
            if action_type == DefensiveAction.SHOT_BLOCK:
                self.game_stats[defending_player.id]['blocked_shots_by'] += 1
        
        # Update team defensive stats
        defending_team = self._get_player_team(defending_player)
        team_name = defending_team.team_name
        
        if team_name in self.team_stats:
            if action_type == DefensiveAction.SHOT_BLOCK:
                self.team_stats[team_name]['blocked_shots_by_team'] += 1

    def _apply_defensive_system(self, defending_team, system_type):
        """
        Stage 4: Apply team defensive system modifiers.
        """
        if system_type == DefensiveSystem.AGGRESSIVE_FORECHECK:
            self.defensive_pressure = 1.3
            self.physical_intensity = 1.2
        elif system_type == DefensiveSystem.DEFENSIVE_SHELL:
            self.defensive_pressure = 0.8
            self.physical_intensity = 0.9
        elif system_type == DefensiveSystem.NEUTRAL_ZONE_TRAP:
            self.defensive_pressure = 1.1
            self.physical_intensity = 1.0
        elif system_type == DefensiveSystem.ZONE_COVERAGE:
            self.defensive_pressure = 1.0
            self.physical_intensity = 1.0
        elif system_type == DefensiveSystem.MAN_TO_MAN:
            self.defensive_pressure = 1.1
            self.physical_intensity = 1.1
        else:  # HYBRID
            self.defensive_pressure = 1.05
            self.physical_intensity = 1.05
        
        self.current_defensive_system = system_type

    def _get_player_team(self, player):
        """Helper method to determine which team a player belongs to."""
        if player in self.home_team.roster:
            return self.home_team
        elif player in self.away_team.roster:
            return self.away_team
        else:
            return None

    # ===== STAGE 5: GOALTENDING EXCELLENCE =====
    
    def _calculate_expected_goal_value(self, shot_location, shot_type, shot_quality, distance):
        """
        Stage 5: Calculate the expected goal value for a shot (xG calculation).
        """
        # Base xG values by shot location (calibrated to NHL ~9% avg conversion)
        base_xg = {
            ShotLocation.CREASE: 0.28,
            ShotLocation.LOW_SLOT: 0.15,
            ShotLocation.HIGH_SLOT: 0.09,
            ShotLocation.LEFT_CIRCLE: 0.07,
            ShotLocation.RIGHT_CIRCLE: 0.07,
            ShotLocation.POINT: 0.03,
            ShotLocation.LEFT_WING: 0.045,
            ShotLocation.RIGHT_WING: 0.045
        }.get(shot_location, 0.06)
        
        # Shot type modifiers
        type_modifier = {
            ShotType.WRIST_SHOT: 1.0,
            ShotType.SLAP_SHOT: 1.1,
            ShotType.SNAP_SHOT: 1.05,
            ShotType.BACKHAND: 0.8,
            ShotType.TIP_IN: 1.3,
            ShotType.DEFLECTION: 1.4,
            ShotType.WRAPAROUND: 0.9,
            ShotType.ONE_TIMER: 1.2,
            ShotType.REBOUND: 1.5
        }.get(shot_type, 1.0)
        
        # Shot quality modifiers
        quality_modifier = {
            'high': 1.3,
            'medium': 1.0,
            'low': 0.7
        }.get(shot_quality, 1.0)
        
        # Distance modifier (closer = higher xG)
        distance_modifier = max(0.3, 1.2 - (distance / 50))
        
        xg = base_xg * type_modifier * quality_modifier * distance_modifier
        return min(xg, 0.95)  # Cap at 95%

    def _determine_goaltender_style(self, goaltender):
        """
        Stage 5: Determine goaltender's playing style based on attributes.
        """
        # Analyze goalie attributes to determine style
        positioning_score = (goaltender.positioning + goaltender.anticipation) / 2
        reflexes_score = goaltender.reflexes
        flexibility = getattr(goaltender, 'flexibility', 15)  # Default if not defined
        
        if positioning_score >= 16:
            return GoaltenderStyle.POSITIONAL
        elif reflexes_score >= 18:
            return GoaltenderStyle.REACTIONARY
        elif flexibility >= 17:
            return GoaltenderStyle.BUTTERFLY
        elif positioning_score >= 14 and reflexes_score >= 15:
            return GoaltenderStyle.HYBRID
        else:
            return GoaltenderStyle.STAND_UP

    def _determine_goal_type(self, shot_type, location, save_type):
        """Classify how a goal beat the goalie (for advanced logging)."""
        if shot_type == ShotType.REBOUND:
            return GoalType.REBOUND
        if shot_type in (ShotType.TIP_IN, ShotType.DEFLECTION):
            return GoalType.DEFLECTION
        if location in (ShotLocation.CREASE, ShotLocation.LOW_SLOT):
            return random.choice([GoalType.FIVE_HOLE, GoalType.SCREEN_SHOT])
        if location in (ShotLocation.LEFT_CIRCLE, ShotLocation.RIGHT_CIRCLE):
            return random.choice([GoalType.TOP_SHELF, GoalType.HIGH_GLOVE,
                                  GoalType.HIGH_BLOCKER])
        if location == ShotLocation.POINT:
            return GoalType.SCREEN_SHOT
        return random.choice([GoalType.LOW_GLOVE, GoalType.LOW_BLOCKER,
                              GoalType.FIVE_HOLE, GoalType.TOP_SHELF])

    def _get_save_type(self, shot_location, shot_type, goaltender_position, goaltender_style):
        """
        Stage 5: Determine the type of save attempt based on shot and goalie positioning.
        """
        # Base probabilities for different save types
        save_probabilities = {
            SaveType.GLOVE_SAVE: 0.2,
            SaveType.BLOCKER_SAVE: 0.2,
            SaveType.PAD_SAVE: 0.3,
            SaveType.STICK_SAVE: 0.1,
            SaveType.CHEST_SAVE: 0.15,
            SaveType.DESPERATION_SAVE: 0.04,
            SaveType.DIVING_SAVE: 0.01
        }
        
        # Adjust probabilities based on shot location
        if shot_location in [ShotLocation.CREASE, ShotLocation.LOW_SLOT]:
            save_probabilities[SaveType.PAD_SAVE] += 0.2
            save_probabilities[SaveType.DESPERATION_SAVE] += 0.1
        elif shot_location in [ShotLocation.LEFT_CIRCLE, ShotLocation.RIGHT_CIRCLE]:
            save_probabilities[SaveType.GLOVE_SAVE] += 0.15
            save_probabilities[SaveType.BLOCKER_SAVE] += 0.15
        elif shot_location == ShotLocation.POINT:
            save_probabilities[SaveType.CHEST_SAVE] += 0.2
            save_probabilities[SaveType.STICK_SAVE] += 0.1
        
        # Adjust based on shot type
        if shot_type in [ShotType.TIP_IN, ShotType.DEFLECTION]:
            save_probabilities[SaveType.DESPERATION_SAVE] += 0.2
            save_probabilities[SaveType.DIVING_SAVE] += 0.1
        elif shot_type == ShotType.REBOUND:
            save_probabilities[SaveType.PAD_SAVE] += 0.3
        
        # Adjust based on goaltender style
        if goaltender_style == GoaltenderStyle.BUTTERFLY:
            save_probabilities[SaveType.PAD_SAVE] += 0.2
        elif goaltender_style == GoaltenderStyle.STAND_UP:
            save_probabilities[SaveType.STICK_SAVE] += 0.15
        elif goaltender_style == GoaltenderStyle.REACTIONARY:
            save_probabilities[SaveType.GLOVE_SAVE] += 0.1
            save_probabilities[SaveType.BLOCKER_SAVE] += 0.1
        
        # Normalize probabilities
        total = sum(save_probabilities.values())
        for save_type in save_probabilities:
            save_probabilities[save_type] /= total
        
        # Select save type based on probabilities
        rand = random.random()
        cumulative = 0
        for save_type, prob in save_probabilities.items():
            cumulative += prob
            if rand < cumulative:
                return save_type
        
        return SaveType.PAD_SAVE  # Default fallback

    def _calculate_save_probability(self, goaltender, shot_location, shot_type, shot_quality, distance, expected_goal):
        """
        Stage 5: Calculate the probability of a save based on goaltender skills and shot characteristics.
        """
        # Base save probability (inverse of expected goal)
        base_save_probability = 1.0 - expected_goal
        
        # Goaltender skill factors
        positioning_skill = (goaltender.positioning + goaltender.anticipation) / 2
        reaction_skill = (goaltender.reflexes + goaltender.agility) / 2
        technique_skill = (goaltender.goaltending + goaltender.rebound_control) / 2
        
        # Overall goaltender skill
        goalie_skill = (positioning_skill + reaction_skill + technique_skill) / 3
        
        # Skill modifier: normalize against the league-average starter skill
        # (measured ~11.6 from the player generator's attribute distribution;
        # an average goalie gets a 1.0 modifier). Dampened 60/40 so the
        # starter talent spread maps to NHL-like sv% ranges instead of
        # producing constant blowouts against weak goalies.
        LEAGUE_AVG_GOALIE_SKILL = 11.6
        skill_modifier = 0.6 + 0.4 * (goalie_skill / LEAGUE_AVG_GOALIE_SKILL)
        
        # Fatigue factor
        fatigue_factor = self.goaltender_fatigue.get(goaltender.id, 100) / 100
        
        # Position modifier
        position = self.goaltender_positioning.get(goaltender.id, GoaltenderPosition.IN_NET)
        position_modifier = {
            GoaltenderPosition.IN_NET: 1.0,
            GoaltenderPosition.CHALLENGING: 1.1,
            GoaltenderPosition.DEEP_NET: 0.9,
            GoaltenderPosition.AGGRESSIVE: 1.15,
            GoaltenderPosition.BUTTERFLY: 1.05,
            GoaltenderPosition.STAND_UP: 0.95
        }.get(position, 1.0)
        
        # Calculate final save probability
        save_probability = base_save_probability * skill_modifier * fatigue_factor * position_modifier
        
        # Apply style-specific modifiers
        goalie_style = self._determine_goaltender_style(goaltender)
        if goalie_style == GoaltenderStyle.POSITIONAL and shot_type in [ShotType.WRIST_SHOT, ShotType.SNAP_SHOT]:
            save_probability *= 1.1
        elif goalie_style == GoaltenderStyle.REACTIONARY and shot_type in [ShotType.TIP_IN, ShotType.DEFLECTION]:
            save_probability *= 1.15
        elif goalie_style == GoaltenderStyle.BUTTERFLY and shot_location in [ShotLocation.LOW_SLOT, ShotLocation.CREASE]:
            save_probability *= 1.1
        
        return min(max(save_probability, 0.05), 0.98)  # Clamp between 5% and 98%

    def _determine_rebound_control(self, goaltender, save_type, shot_type, shot_power):
        """
        Stage 5: Determine how well the goaltender controls the rebound.
        """
        # Base rebound control based on goaltender's rebound control attribute
        # Calibrated so an average goalie (~12) controls ~80% of saves cleanly;
        # elite goalies ~95%, weak ones ~70% (before save/shot modifiers)
        base_control = 0.5 + (goaltender.rebound_control / 20.0) * 0.5
        
        # Save type modifiers
        save_type_modifier = {
            SaveType.GLOVE_SAVE: 1.3,      # Glove saves usually absorb the puck
            SaveType.CHEST_SAVE: 1.2,     # Chest saves tend to be controlled
            SaveType.STICK_SAVE: 0.7,     # Stick saves often create rebounds
            SaveType.PAD_SAVE: 0.8,       # Pad saves can create rebounds
            SaveType.BLOCKER_SAVE: 0.6,   # Blocker saves often kick out rebounds
            SaveType.DESPERATION_SAVE: 0.4, # Desperation saves rarely controlled
            SaveType.DIVING_SAVE: 0.5     # Diving saves often uncontrolled
        }.get(save_type, 1.0)
        
        # Shot type modifiers
        shot_type_modifier = {
            ShotType.SLAP_SHOT: 0.7,      # Hard shots harder to control
            ShotType.ONE_TIMER: 0.6,      # One-timers hard to control
            ShotType.TIP_IN: 0.5,         # Tips very hard to control
            ShotType.DEFLECTION: 0.4,     # Deflections extremely hard to control
            ShotType.REBOUND: 0.8         # Rebounds somewhat easier
        }.get(shot_type, 1.0)
        
        # Calculate final rebound control probability
        control_probability = min(base_control * save_type_modifier * shot_type_modifier, 0.97)

        # Determine rebound outcome: controlled outcomes scale with the
        # goalie's control; the remainder become rebound chances
        # (split weak/dangerous for flavor)
        rand = random.random()
        if rand < control_probability * 0.45:
            return ReboundControl.ABSORBED
        elif rand < control_probability * 0.75:
            return ReboundControl.CONTROLLED
        elif rand < control_probability:
            return ReboundControl.DEFLECTED_AWAY
        elif rand < control_probability + (1 - control_probability) * 0.7:
            return ReboundControl.WEAK_REBOUND
        else:
            return ReboundControl.DANGEROUS_REBOUND

    def _record_goaltender_stats(self, goaltender, shot_result, save_type, expected_goal, shot_quality):
        """
        Stage 5: Record detailed goaltending statistics.
        """
        goalie_id = goaltender.id
        defending_team = self._get_player_team(goaltender)
        team_name = defending_team.team_name
        
        # Update individual goalie stats
        if goalie_id in self.game_stats:
            self.game_stats[goalie_id]['shots_against'] += 1
            
            if shot_result == 'save':
                self.game_stats[goalie_id]['saves'] += 1
                
                # Record save by type
                save_type_attr = f"{save_type.value}_saves"
                if save_type_attr in self.game_stats[goalie_id]:
                    self.game_stats[goalie_id][save_type_attr] += 1
                
                # Record save by danger level
                if shot_quality == 'high':
                    self.game_stats[goalie_id]['high_danger_saves'] += 1
                elif shot_quality == 'medium':
                    self.game_stats[goalie_id]['medium_danger_saves'] += 1
                else:
                    self.game_stats[goalie_id]['low_danger_saves'] += 1
                    
            elif shot_result == 'goal':
                self.game_stats[goalie_id]['goals_against'] += 1
            
            # Update save percentage
            shots_against = self.game_stats[goalie_id]['shots_against']
            saves = self.game_stats[goalie_id]['saves']
            if shots_against > 0:
                self.game_stats[goalie_id]['save_percentage'] = (saves / shots_against) * 100
        
        # Update team goaltending stats
        if team_name in self.team_stats:
            self.team_stats[team_name]['shots_against'] += 1
            
            if shot_result == 'save':
                self.team_stats[team_name]['saves'] += 1
                
                if shot_quality == 'high':
                    self.team_stats[team_name]['high_danger_saves'] += 1
                elif shot_quality == 'medium':
                    self.team_stats[team_name]['medium_danger_saves'] += 1
                else:
                    self.team_stats[team_name]['low_danger_saves'] += 1
                    
            elif shot_result == 'goal':
                self.team_stats[team_name]['goals_against'] += 1
            
            # Update team save percentage
            team_shots = self.team_stats[team_name]['shots_against']
            team_saves = self.team_stats[team_name]['saves']
            if team_shots > 0:
                self.team_stats[team_name]['team_save_percentage'] = (team_saves / team_shots) * 100
        
        # Update GSAx tracking
        if goalie_id in self.save_quality_tracking:
            self.save_quality_tracking[goalie_id]['total_expected_goals_against'] += expected_goal
            
            if shot_result == 'goal':
                self.save_quality_tracking[goalie_id]['actual_goals_against'] += 1
            
            # Calculate Goals Saved Above Expected
            expected_ga = self.save_quality_tracking[goalie_id]['total_expected_goals_against']
            actual_ga = self.save_quality_tracking[goalie_id]['actual_goals_against']
            gsax = expected_ga - actual_ga
            
            # Update individual and team GSAx
            self.game_stats[goalie_id]['goals_saved_above_expected'] = round(gsax, 2)
            self.team_stats[team_name]['goals_saved_above_expected'] = round(gsax, 2)

    def _update_goaltender_fatigue(self, goaltender, shot_difficulty):
        """
        Stage 5: Update goaltender fatigue based on saves and shot difficulty.
        """
        if goaltender.id in self.goaltender_fatigue:
            # Base fatigue loss per shot
            fatigue_loss = 0.1
            
            # Additional fatigue for difficult saves
            if shot_difficulty == 'high':
                fatigue_loss += 0.3
            elif shot_difficulty == 'medium':
                fatigue_loss += 0.1
            
            self.goaltender_fatigue[goaltender.id] = max(0, 
                self.goaltender_fatigue[goaltender.id] - fatigue_loss)

    def _adjust_goaltender_positioning(self, goaltender, shot_location, situation):
        """
        Stage 5: Dynamically adjust goaltender positioning based on game situation.
        """
        # Determine optimal positioning based on shot location and situation
        if shot_location in [ShotLocation.CREASE, ShotLocation.LOW_SLOT]:
            # Close shots - challenge the shooter
            self.goaltender_positioning[goaltender.id] = GoaltenderPosition.CHALLENGING
        elif shot_location == ShotLocation.POINT:
            # Point shots - stay deep for screen/deflection
            self.goaltender_positioning[goaltender.id] = GoaltenderPosition.DEEP_NET
        elif situation in [SpecialSituation.PENALTY_KILL]:
            # Penalty kill - more aggressive positioning
            self.goaltender_positioning[goaltender.id] = GoaltenderPosition.AGGRESSIVE
        else:
            # Default positioning
            self.goaltender_positioning[goaltender.id] = GoaltenderPosition.IN_NET

    # ===== STAGE 6: CHEMISTRY & COACHING METHODS =====
    
    def _apply_chemistry_bonus(self, player, action_type='general'):
        """
        Stage 6: Apply chemistry bonuses to player actions based on linemates.
        """
        if player.id not in self.game_stats:
            return 1.0
        
        # Get current linemates (simplified - assume top 6 players on ice)
        team = self._get_player_team(player)
        if not team:
            return 1.0
        
        on_ice_teammates = [p for p in self._get_on_ice(team) if p != player and p.primary_position != PlayerPosition.GOALIE]
        
        if not on_ice_teammates:
            return 1.0
        
        # Calculate average chemistry with current linemates
        total_chemistry = 0
        chemistry_count = 0
        
        for teammate in on_ice_teammates:
            if ('linemate_synergy' in self.game_stats[player.id] and 
                teammate.id in self.game_stats[player.id]['linemate_synergy']):
                chemistry = self.game_stats[player.id]['linemate_synergy'][teammate.id]
                total_chemistry += chemistry
                chemistry_count += 1
        
        if chemistry_count == 0:
            return 1.0
        
        avg_chemistry = total_chemistry / chemistry_count
        
        # Convert chemistry rating to bonus multiplier
        if avg_chemistry >= 85:
            bonus_multiplier = 1.15  # Excellent chemistry
        elif avg_chemistry >= 70:
            bonus_multiplier = 1.10  # Good chemistry
        elif avg_chemistry >= 55:
            bonus_multiplier = 1.05  # Above average chemistry
        elif avg_chemistry >= 40:
            bonus_multiplier = 1.0   # Neutral chemistry
        else:
            bonus_multiplier = 0.90  # Poor chemistry
        
        # Action-specific bonuses
        if action_type == 'passing' and avg_chemistry >= 75:
            bonus_multiplier += 0.05  # Extra passing bonus for good chemistry
        elif action_type == 'shooting' and avg_chemistry >= 80:
            bonus_multiplier += 0.03  # Shooting bonus from setup plays
        elif action_type == 'defensive' and avg_chemistry >= 70:
            bonus_multiplier += 0.04  # Defensive coordination bonus
        
        # Update player stats
        self.game_stats[player.id]['chemistry_bonus'] = bonus_multiplier - 1.0
        
        return bonus_multiplier

    def _apply_coaching_adjustments(self, team, situation):
        """
        Stage 6: Apply coaching bonuses based on game situation and team strategy.
        """
        team_name = team.team_name
        
        # Get base coaching adjustment for situation
        base_adjustment = self.coaching_adjustments.get(situation, {}).get(
            'home' if team == self.home_team else 'away', 1.0
        )
        
        # Tactical system bonuses
        tactical_bonus = self._get_tactical_system_bonus(situation)
        
        # Special situation coaching
        situational_bonus = 1.0
        if situation == SpecialSituation.POWER_PLAY:
            # Power play coaching effectiveness
            situational_bonus = 1.08 + (random.random() * 0.04)  # 8-12% bonus
        elif situation == SpecialSituation.PENALTY_KILL:
            # Penalty kill coaching effectiveness  
            situational_bonus = 1.06 + (random.random() * 0.04)  # 6-10% bonus
        elif situation in [SpecialSituation.FOUR_ON_FOUR, SpecialSituation.THREE_ON_THREE]:
            # Open ice coaching
            situational_bonus = 1.05 + (random.random() * 0.05)  # 5-10% bonus
        
        total_adjustment = base_adjustment * tactical_bonus * situational_bonus
        
        # Track coaching adjustments
        if team_name in self.team_stats:
            self.team_stats[team_name]['coaching_adjustments'] += 1
        
        return total_adjustment

    def _team_situation(self, team, situation):
        """Translate the home-centric situation to the given team's perspective."""
        if team == self.home_team:
            return situation
        swap = {SpecialSituation.POWER_PLAY: SpecialSituation.PENALTY_KILL,
                SpecialSituation.PENALTY_KILL: SpecialSituation.POWER_PLAY}
        return swap.get(situation, situation)

    def _team_tactical_system(self, team):
        """Map a team's even-strength tactic choice to the sim's tactical system."""
        es = getattr(team, 'tactic_even_strength', 'Balanced')
        return {
            'Very Defensive': TacticalSystem.NEUTRAL_ZONE_TRAP,
            'Defensive': TacticalSystem.NEUTRAL_ZONE_TRAP,
            'Balanced': TacticalSystem.CYCLE_GAME,
            'Offensive': TacticalSystem.AGGRESSIVE_FORECHECK,
            'Very Offensive': TacticalSystem.RUSH_OFFENSE,
        }.get(es, TacticalSystem.CYCLE_GAME)

    def _team_tactics_xg_factor(self, attacking_team, defending_team):
        """xG multiplier from both teams' tactic settings.

        Even-strength style boosts your own finishing and suppresses (or
        leaks) opponent chances; special-teams approach moves power-play
        and penalty-kill efficiency. Net effect is ~+/-8% per side.
        """
        situation = self._get_current_situation()
        sit_att = self._team_situation(attacking_team, situation)
        sit_def = self._team_situation(defending_team, situation)

        es_attack = {'Very Defensive': 0.94, 'Defensive': 0.97, 'Balanced': 1.0,
                     'Offensive': 1.04, 'Very Offensive': 1.08}
        es_defense = {'Very Defensive': 0.92, 'Defensive': 0.96, 'Balanced': 1.0,
                      'Offensive': 1.03, 'Very Offensive': 1.06}
        factor = (es_attack.get(getattr(attacking_team, 'tactic_even_strength', 'Balanced'), 1.0)
                  * es_defense.get(getattr(defending_team, 'tactic_even_strength', 'Balanced'), 1.0))

        # Special-teams approach
        if sit_att == SpecialSituation.POWER_PLAY:
            pp = getattr(attacking_team, 'tactic_power_play', 'Offensive')
            factor *= {'Conservative': 0.96, 'Balanced': 1.0, 'Offensive': 1.05,
                       'Very Offensive': 1.10}.get(pp, 1.05)
            pk = getattr(defending_team, 'tactic_penalty_kill', 'Defensive')
            factor /= {'Very Defensive': 1.10, 'Defensive': 1.05, 'Balanced': 1.0,
                       'Aggressive': 0.96}.get(pk, 1.05)
        elif sit_def == SpecialSituation.POWER_PLAY:
            # Attacking team is shorthanded: their PK approach suppresses own xG slightly
            pk = getattr(attacking_team, 'tactic_penalty_kill', 'Defensive')
            factor *= {'Very Defensive': 0.94, 'Defensive': 0.97, 'Balanced': 1.0,
                       'Aggressive': 1.02}.get(pk, 0.97)

        return max(0.8, min(1.25, factor))

    def _get_tactical_system_bonus(self, team, situation):
        """
        Stage 6: Get tactical system effectiveness bonus for the given team
        and situation, based on that team's even-strength tactic setting.
        """
        system = self._team_tactical_system(team)
        system_bonuses = {
            TacticalSystem.CYCLE_GAME: {
                SpecialSituation.EVEN_STRENGTH: 1.05,
                SpecialSituation.POWER_PLAY: 1.08,
                SpecialSituation.PENALTY_KILL: 1.02
            },
            TacticalSystem.RUSH_OFFENSE: {
                SpecialSituation.EVEN_STRENGTH: 1.04,
                SpecialSituation.FOUR_ON_FOUR: 1.10,
                SpecialSituation.THREE_ON_THREE: 1.15
            },
            TacticalSystem.AGGRESSIVE_FORECHECK: {
                SpecialSituation.EVEN_STRENGTH: 1.06,
                SpecialSituation.PENALTY_KILL: 1.08,
                SpecialSituation.POWER_PLAY: 1.03
            },
            TacticalSystem.NEUTRAL_ZONE_TRAP: {
                SpecialSituation.EVEN_STRENGTH: 1.03,
                SpecialSituation.PENALTY_KILL: 1.12,
                SpecialSituation.POWER_PLAY: 0.98
            }
        }
        
        return system_bonuses.get(system, {}).get(situation, 1.0)

    def _calculate_role_bonus(self, player, action_type):
        """
        Stage 6: Calculate role-specific performance bonus.
        """
        if player.id not in self.role_performance:
            return 1.0
        
        role = self.role_performance[player.id]['role']
        effectiveness = self.role_performance[player.id]['effectiveness']
        
        # Base role bonus from effectiveness
        role_bonus = 0.8 + (effectiveness / 100.0) * 0.4  # 0.8-1.2 range
        
        # Action-specific role bonuses
        if action_type == 'shooting':
            if role == LineRole.PRIMARY_SCORER:
                role_bonus += 0.1
            elif role == LineRole.POWER_PLAY_SPECIALIST:
                role_bonus += 0.08
        elif action_type == 'passing':
            if role == LineRole.PLAYMAKER:
                role_bonus += 0.12
            elif role == LineRole.OFFENSIVE_DEFENDER:
                role_bonus += 0.06
        elif action_type == 'defensive':
            if role == LineRole.SHUTDOWN_DEFENDER:
                role_bonus += 0.15
            elif role == LineRole.DEFENSIVE_FORWARD:
                role_bonus += 0.10
            elif role == LineRole.PENALTY_KILLER:
                role_bonus += 0.12
        elif action_type == 'physical':
            if role == LineRole.ENFORCER:
                role_bonus += 0.20
            elif role == LineRole.POWER_FORWARD:
                role_bonus += 0.15
        
        # Update player stats
        if player.id in self.game_stats:
            self.game_stats[player.id]['coaching_bonus'] = role_bonus - 1.0
        
        return role_bonus

    def _update_chemistry_through_play(self, player1, player2, event_type, success=True):
        """
        Stage 6: Update chemistry between players based on game events.
        """
        if (player1.id not in self.game_stats or player2.id not in self.game_stats):
            return
        
        # Ensure linemate synergy exists
        for player in [player1, player2]:
            if 'linemate_synergy' not in self.game_stats[player.id]:
                self.game_stats[player.id]['linemate_synergy'] = {}
        
        # Get current chemistry between players
        current_chemistry_1_2 = self.game_stats[player1.id]['linemate_synergy'].get(player2.id, 50.0)
        current_chemistry_2_1 = self.game_stats[player2.id]['linemate_synergy'].get(player1.id, 50.0)
        
        # Chemistry change based on event type and success
        chemistry_change = 0
        
        if event_type == 'goal_assist' and success:
            chemistry_change = 2.0  # Big positive boost for goal+assist
        elif event_type == 'pass_completion' and success:
            chemistry_change = 0.3  # Small boost for successful passes
        elif event_type == 'defensive_play' and success:
            chemistry_change = 0.5  # Boost for defensive coordination
        elif event_type == 'failed_pass' and not success:
            chemistry_change = -0.2  # Small penalty for failed connection
        elif event_type == 'turnover' and not success:
            chemistry_change = -0.4  # Larger penalty for turnovers
        elif event_type == 'argument':
            chemistry_change = -1.0  # Penalty for conflict
        
        # Apply personality modifiers
        if player1.teamwork >= 15 and player2.teamwork >= 15:
            chemistry_change *= 1.2  # High teamwork players build chemistry faster
        
        if abs(player1.leadership - player2.leadership) >= 5:
            chemistry_change *= 0.8  # Leadership conflicts slow chemistry growth
        
        # Update chemistry (capped at 0-100)
        new_chemistry_1_2 = max(0, min(100, current_chemistry_1_2 + chemistry_change))
        new_chemistry_2_1 = max(0, min(100, current_chemistry_2_1 + chemistry_change))
        
        self.game_stats[player1.id]['linemate_synergy'][player2.id] = new_chemistry_1_2
        self.game_stats[player2.id]['linemate_synergy'][player1.id] = new_chemistry_2_1
        
        # Track chemistry evolution
        if chemistry_change > 0:
            if 'positive_events' not in self.chemistry_evolution:
                self.chemistry_evolution['positive_events'] = {}
            pair_key = f"{min(player1.id, player2.id)}_{max(player1.id, player2.id)}"
            self.chemistry_evolution['positive_events'][pair_key] = self.chemistry_evolution['positive_events'].get(pair_key, 0) + 1
        elif chemistry_change < 0:
            if 'negative_events' not in self.chemistry_evolution:
                self.chemistry_evolution['negative_events'] = {}
            pair_key = f"{min(player1.id, player2.id)}_{max(player1.id, player2.id)}"
            self.chemistry_evolution['negative_events'][pair_key] = self.chemistry_evolution['negative_events'].get(pair_key, 0) + 1

    def _evaluate_line_matchup(self, attacking_line, defending_line):
        """
        Stage 6: Evaluate the effectiveness of one line against another.
        """
        if not attacking_line or not defending_line:
            return 1.0
        
        # Calculate average ratings for each line
        attacking_strength = sum(p.overall_rating() for p in attacking_line) / len(attacking_line)
        defending_strength = sum(p.overall_rating() for p in defending_line) / len(defending_line)
        
        # Get line chemistry bonuses
        attacking_chemistry = self._get_line_chemistry_average(attacking_line)
        defending_chemistry = self._get_line_chemistry_average(defending_line)
        
        # Calculate chemistry-adjusted strength
        attacking_adjusted = attacking_strength * (1 + (attacking_chemistry - 50) / 200)
        defending_adjusted = defending_strength * (1 + (defending_chemistry - 50) / 200)
        
        # Matchup advantage calculation
        strength_diff = attacking_adjusted - defending_adjusted
        matchup_bonus = 1.0 + (strength_diff / 100)  # Convert rating difference to multiplier
        
        # Clamp the bonus to reasonable range
        matchup_bonus = max(0.7, min(1.4, matchup_bonus))
        
        # Track line matchup data
        for player in attacking_line:
            if player.id in self.game_stats:
                if matchup_bonus > 1.05:
                    self.game_stats[player.id]['line_matching_advantage'] += 1
        
        return matchup_bonus

    def _get_line_chemistry_average(self, players):
        """
        Stage 6: Get average chemistry rating for a group of players.
        """
        if len(players) < 2:
            return 50.0
        
        total_chemistry = 0
        comparisons = 0
        
        for i, player1 in enumerate(players):
            for j, player2 in enumerate(players):
                if i != j and player1.id in self.game_stats and player2.id in self.game_stats:
                    if ('linemate_synergy' in self.game_stats[player1.id] and 
                        player2.id in self.game_stats[player1.id]['linemate_synergy']):
                        chemistry = self.game_stats[player1.id]['linemate_synergy'][player2.id]
                        total_chemistry += chemistry
                        comparisons += 1
        
        return total_chemistry / comparisons if comparisons > 0 else 50.0

    # ===== STAGE 7: MICRO-EVENTS & GAME FLOW METHODS =====
    
    def _track_micro_event(self, event_type, player=None, details=None):
        """
        Stage 7: Track and log micro-events during gameplay.
        """
        micro_event = {
            'event_type': event_type,
            'player': player,
            'details': details or {},
            'time': self.clock,
            'period': self.period,
            'momentum': self.momentum,
            'flow': self.game_flow,
            'pressure': self.pressure_level
        }
        
        self.micro_events.append(micro_event)
        
        # Update player statistics
        if player and player.id in self.game_stats:
            if event_type in [MicroEventType.MOMENTUM_SHIFT, MicroEventType.CONFIDENCE_BOOST]:
                self.game_stats[player.id]['momentum_events'] += 1
            elif event_type in [MicroEventType.PRESSURE_APPLICATION]:
                self.game_stats[player.id]['pressure_applied'] += 0.1
            elif event_type in [MicroEventType.PLAYER_COMMUNICATION, MicroEventType.CAPTAIN_LEADERSHIP]:
                self.game_stats[player.id]['communication_events'] += 1
                if player.captaincy:
                    self.game_stats[player.id]['leadership_moments'] += 1
    
    def _update_momentum(self, triggering_event, intensity=1):
        """
        Stage 7: Update game momentum based on events.
        """
        momentum_change = 0
        team_benefiting = None
        
        # Determine momentum impact based on event type
        if triggering_event == 'goal':
            momentum_change = 2 * intensity
        elif triggering_event == 'big_hit':
            momentum_change = 1 * intensity
        elif triggering_event == 'save':
            momentum_change = 1 * intensity
        elif triggering_event == 'penalty':
            momentum_change = -1 * intensity
        elif triggering_event == 'turnover':
            momentum_change = 1 * intensity
        elif triggering_event == 'fight':
            momentum_change = 2 * intensity
        
        # Apply momentum change
        current_value = list(GameMomentum).index(self.momentum) - 3  # Convert to -3 to +3 scale
        new_value = max(-3, min(3, current_value + momentum_change))
        self.momentum = list(GameMomentum)[new_value + 3]  # Convert back to enum
        
        # Track momentum history
        self.momentum_history.append({
            'time': self.clock,
            'period': self.period,
            'momentum': self.momentum,
            'trigger': triggering_event,
            'intensity': intensity
        })
        
        # Update team statistics
        for team_name in self.team_stats:
            if new_value > current_value:  # Momentum increased
                self.team_stats[team_name]['momentum_shifts'] += 1
    
    def _update_game_flow(self, factors):
        """
        Stage 7: Update game flow based on multiple factors.
        """
        flow_adjustment = 0
        
        # Factors that affect game flow
        if 'penalties' in factors:
            flow_adjustment -= 1  # Penalties slow the game
        if 'hits' in factors:
            flow_adjustment += 1  # Hitting speeds up the game
        if 'line_changes' in factors:
            flow_adjustment -= 0.5  # Frequent line changes slow the game
        if 'turnovers' in factors:
            flow_adjustment += 1  # Turnovers create fast play
        if 'momentum' in factors:
            momentum_value = list(GameMomentum).index(self.momentum) - 3
            flow_adjustment += abs(momentum_value) * 0.3  # High momentum = faster play
        
        # Convert current flow to numeric value
        flow_values = [GameFlow.VERY_SLOW, GameFlow.SLOW, GameFlow.NORMAL, 
                      GameFlow.FAST, GameFlow.VERY_FAST, GameFlow.FRANTIC]
        current_index = flow_values.index(self.game_flow)
        
        # Apply adjustment
        new_index = max(0, min(len(flow_values) - 1, current_index + int(flow_adjustment)))
        self.game_flow = flow_values[new_index]
        
        # Update flow multipliers
        flow_multiplier = [0.7, 0.85, 1.0, 1.15, 1.3, 1.5][new_index]
        self.flow_multipliers['shot_frequency'] = flow_multiplier
        self.flow_multipliers['mistake_likelihood'] = 2.0 - flow_multiplier  # Faster = more mistakes
    
    def _calculate_pressure_level(self, zone, attacking_team):
        """
        Stage 7: Calculate current pressure level in a zone.
        """
        pressure = 0
        
        # Base pressure from zone control
        if zone == 'offensive_zone':
            pressure += 40
        elif zone == 'neutral_zone':
            pressure += 20
        elif zone == 'defensive_zone':
            pressure += 10
        
        # Momentum impact on pressure
        momentum_value = list(GameMomentum).index(self.momentum) - 3
        pressure += momentum_value * 10
        
        # Game flow impact
        flow_values = [GameFlow.VERY_SLOW, GameFlow.SLOW, GameFlow.NORMAL, 
                      GameFlow.FAST, GameFlow.VERY_FAST, GameFlow.FRANTIC]
        flow_index = flow_values.index(self.game_flow)
        pressure += (flow_index - 2) * 5
        
        # Constrain to 0-100 range
        pressure = max(0, min(100, pressure))
        
        # Convert to pressure level enum
        if pressure <= 20:
            self.pressure_level = PressureLevel.MINIMAL
        elif pressure <= 40:
            self.pressure_level = PressureLevel.LOW
        elif pressure <= 60:
            self.pressure_level = PressureLevel.MODERATE
        elif pressure <= 80:
            self.pressure_level = PressureLevel.HIGH
        else:
            self.pressure_level = PressureLevel.INTENSE
        
        return pressure
    
    def _determine_situational_context(self):
        """
        Stage 9: Determine current situational context for AI decision making.
        """
        # Check special situations first (highest priority)
        if hasattr(self, 'current_situation') and self.current_situation == SpecialSituation.POWER_PLAY:
            self.situational_context = SituationalContext.POWER_PLAY_OPPORTUNITY
        elif hasattr(self, 'current_situation') and self.current_situation == SpecialSituation.PENALTY_KILL:
            self.situational_context = SituationalContext.PENALTY_KILL_SITUATION
        # Check overtime
        elif self.period > 3:
            self.situational_context = SituationalContext.OVERTIME_SITUATION
        # Check time-based contexts
        elif self.period >= 3 and (1200 - self.clock) / 60 > 18.0:  # Convert to minutes elapsed
            # Check if trailing or leading in final minutes
            score_diff = self.home_team.goals - self.away_team.goals
            if score_diff < -1:  # Home team trailing by 2+
                self.situational_context = SituationalContext.TRAILING_LATE
            elif score_diff > 1:  # Home team leading by 2+
                self.situational_context = SituationalContext.LEADING_LATE
            else:
                self.situational_context = SituationalContext.DESPERATION_TIME
        elif (1200 - self.clock) / 60 > 19.0:
            self.situational_context = SituationalContext.PERIOD_END
        elif (1200 - self.clock) / 60 > 15.0 and self.pressure_level in [PressureLevel.HIGH, PressureLevel.INTENSE]:
            if list(GameMomentum).index(self.momentum) > 3:
                self.situational_context = SituationalContext.MOMENTUM_SHIFT
            else:
                self.situational_context = SituationalContext.CLOSE_GAME_LATE
        else:
            # Check score-based contexts
            score_diff = abs(self.home_team.goals - self.away_team.goals)
            if score_diff >= 3:
                self.situational_context = SituationalContext.DOMINANT_PERFORMANCE
            elif self.period >= 3 and score_diff <= 1:
                self.situational_context = SituationalContext.CLOSE_GAME_LATE
            elif (1200 - self.clock) < 60:  # Less than 1 minute left
                self.situational_context = SituationalContext.PERIOD_START
            else:
                self.situational_context = SituationalContext.GAME_OPENING
        
        return self.situational_context
    
    def _get_situational_multiplier(self, action_type, player):
        """
        Stage 7: Get performance multiplier based on current situation.
        """
        multiplier = 1.0
        
        # Pressure-based adjustments
        if self.pressure_level == PressureLevel.INTENSE:
            if player.composure >= 16:
                multiplier *= 1.1  # High composure players thrive under pressure
            else:
                multiplier *= 0.9  # Others struggle
        elif self.pressure_level == PressureLevel.MINIMAL:
            if player.focus >= 16:
                multiplier *= 1.05  # High focus maintains performance
            else:
                multiplier *= 0.95  # Others get complacent
        
        # Momentum-based adjustments
        momentum_value = list(GameMomentum).index(self.momentum) - 3
        if abs(momentum_value) >= 2:  # High momentum situations
            if player.confidence >= 16:
                multiplier *= 1.05  # Confident players ride momentum
            if action_type == 'offensive' and momentum_value > 0:
                multiplier *= 1.1  # Positive momentum helps offense
            elif action_type == 'defensive' and momentum_value < 0:
                multiplier *= 1.1  # Negative momentum helps defense
        
        # Flow-based adjustments
        flow_values = [GameFlow.VERY_SLOW, GameFlow.SLOW, GameFlow.NORMAL, 
                      GameFlow.FAST, GameFlow.VERY_FAST, GameFlow.FRANTIC]
        flow_index = flow_values.index(self.game_flow)
        
        if flow_index >= 4:  # Very fast or frantic
            if player.speed >= 16 and player.agility >= 16:
                multiplier *= 1.1  # Fast players excel in fast games
            else:
                multiplier *= 0.95  # Slower players struggle
        elif flow_index <= 1:  # Very slow or slow
            if player.hockey_iq >= 16:
                multiplier *= 1.05  # Smart players excel in slow games
        
        return multiplier
    
    def _process_transition_sequence(self, sequence_type, players_involved):
        """
        Stage 7: Process complex transition sequences (zone entries, rushes, etc.).
        """
        sequence = {
            'type': sequence_type,
            'players': players_involved,
            'time': self.clock,
            'period': self.period,
            'success': False,
            'micro_events': []
        }
        
        # Simulate micro-events within the sequence
        success_probability = 0.5
        
        for player in players_involved:
            # Track micro-events for each player
            self._track_micro_event(MicroEventType.POSITION_CHANGE, player)
            
            # Adjust success probability based on player attributes
            if sequence_type == 'zone_entry':
                success_probability += (player.skating + player.deking) / 200
            elif sequence_type == 'rush':
                success_probability += (player.speed + player.passing) / 200
            elif sequence_type == 'cycle':
                success_probability += (player.puck_protection + player.vision) / 200
            
            # Apply situational multipliers
            situational_mult = self._get_situational_multiplier('offensive', player)
            success_probability *= situational_mult
        
        # Determine success
        sequence['success'] = random.random() < success_probability
        
        # Update statistics
        for player in players_involved:
            if player.id in self.game_stats:
                if sequence['success']:
                    self.game_stats[player.id]['transition_success'] += 1
                else:
                    self.game_stats[player.id]['transition_failures'] += 1
        
        self.transition_sequences.append(sequence)
        return sequence['success']

    # ===== STAGE 8: ADVANCED ANALYTICS INTEGRATION METHODS =====

    def _calculate_expected_goals(self, shot_data):
        """
        Stage 8: Calculate expected goals (xG) for a shot attempt.
        """
        base_xg = 0.1  # Base conversion rate
        
        # Distance factor (closer = higher xG)
        distance_factor = max(0.1, 1.0 - (shot_data.get('distance', 30) / 100))
        
        # Angle factor (better angle = higher xG)
        angle_factor = max(0.3, 1.0 - abs(shot_data.get('angle', 0)) / 90)
        
        # Shot type multiplier
        shot_type_multipliers = {
            ShotType.REBOUND: 2.5,
            ShotType.TIP_IN: 2.0,
            ShotType.ONE_TIMER: 1.8,
            ShotType.BREAKAWAY: 3.0,
            ShotType.SLAP_SHOT: 1.2,
            ShotType.WRIST_SHOT: 1.0,
            ShotType.SNAP_SHOT: 1.1,
            ShotType.BACKHAND: 0.8,
            ShotType.WRAPAROUND: 0.6
        }
        
        shot_type = shot_data.get('shot_type', ShotType.WRIST_SHOT)
        type_multiplier = shot_type_multipliers.get(shot_type, 1.0)
        
        # Traffic factor (more traffic = higher xG for deflections, lower for clean shots)
        traffic = shot_data.get('traffic', 0)
        if shot_type in [ShotType.TIP_IN, ShotType.DEFLECTION]:
            traffic_factor = 1.0 + (traffic * 0.3)
        else:
            traffic_factor = max(0.7, 1.0 - (traffic * 0.2))
        
        # Rush factor (rush shots are slightly easier)
        rush_factor = 1.3 if shot_data.get('rush', False) else 1.0
        
        # Situational factor
        situation_multipliers = {
            SpecialSituation.POWER_PLAY: 1.4,
            SpecialSituation.PENALTY_KILL: 0.6,
            SpecialSituation.FOUR_ON_FOUR: 1.2,
            SpecialSituation.THREE_ON_THREE: 1.5,
            SpecialSituation.EVEN_STRENGTH: 1.0
        }
        
        situation_factor = situation_multipliers.get(self.current_situation, 1.0)
        
        # Calculate final xG
        expected_goals = (base_xg * distance_factor * angle_factor * 
                         type_multiplier * traffic_factor * rush_factor * situation_factor)
        
        return min(0.8, max(0.01, expected_goals))  # Cap between 1% and 80%

    def _update_win_probability(self):
        """
        Stage 8: Update real-time win probability based on current game state.
        """
        # Base probability from score differential
        score_diff = self.home_score - self.away_score
        time_remaining = self.clock + (1200 * (3 - self.period))
        
        # Score differential impact (improved sigmoid function)
        if score_diff == 0:
            score_factor = 0.5  # Tied game
        else:
            # Use tanh for better score differential handling
            score_factor = 0.5 + (math.tanh(score_diff * 0.7) * 0.4)
        
        # Time remaining impact
        time_factor = time_remaining / 3600  # Normalize to game length
        
        # Momentum factor
        momentum_values = {
            GameMomentum.HEAVILY_FAVORING_HOME: 0.7,
            GameMomentum.FAVORING_HOME: 0.6,
            GameMomentum.SLIGHTLY_FAVORING_HOME: 0.55,
            GameMomentum.NEUTRAL: 0.5,
            GameMomentum.SLIGHTLY_FAVORING_AWAY: 0.45,
            GameMomentum.FAVORING_AWAY: 0.4,
            GameMomentum.HEAVILY_FAVORING_AWAY: 0.3
        }
        
        momentum_factor = momentum_values.get(self.momentum, 0.5)
        
        # Special situations impact
        special_teams_factor = 0.5  # Default neutral
        if self.current_situation == SpecialSituation.POWER_PLAY:
            special_teams_factor = 0.65 if len(self.home_penalties) < len(self.away_penalties) else 0.35
        
        # Combine factors (weighted average)
        weights = {
            'score': 0.4,
            'time': 0.2,
            'momentum': 0.25,
            'special_teams': 0.15
        }
        
        win_prob = (score_factor * weights['score'] + 
                   (1.0 - time_factor) * weights['time'] +  # Less time = more certainty
                   momentum_factor * weights['momentum'] +
                   special_teams_factor * weights['special_teams'])
        
        self.win_probability = max(0.01, min(0.99, win_prob))
        
        # Update prediction model history
        self.prediction_models[AnalyticsModel.WIN_PROBABILITY]['history'].append({
            'time': self.clock,
            'period': self.period,
            'probability': self.win_probability,
            'score_home': self.home_score,
            'score_away': self.away_score
        })

    def _calculate_player_war(self, player):
        """
        Stage 8: Calculate Wins Above Replacement (WAR) for a player.
        """
        if player.id not in self.game_stats:
            return 0.0
        
        stats = self.game_stats[player.id]
        replacement_level = self.player_war_tracking[player.id]['replacement_level']
        
        # Offensive contribution
        offensive_war = ((stats['g'] * 3 + stats['a'] * 2) * 0.1) - replacement_level
        
        # Defensive contribution (more complex, based on possession metrics)
        defensive_war = ((stats['takeaways'] - stats['giveaways']) * 0.05 +
                        stats['blocked_shots'] * 0.02 +
                        stats['hits'] * 0.01) - (replacement_level * 0.5)
        
        # Special teams contribution
        special_teams_war = (stats['power_play_goals'] * 0.15 +
                           stats['short_handed_goals'] * 0.25) - (replacement_level * 0.2)
        
        # Ice time factor (more ice time = more opportunity for impact)
        ice_time_factor = stats.get('ice_time', 1000) / 1200  # Normalize to full game
        
        total_war = (offensive_war + defensive_war + special_teams_war) * ice_time_factor
        
        # Update tracking
        self.player_war_tracking[player.id]['offense_war'] = offensive_war
        self.player_war_tracking[player.id]['defense_war'] = defensive_war
        self.player_war_tracking[player.id]['special_teams_war'] = special_teams_war
        self.player_war_tracking[player.id]['total_war'] = total_war
        
        return total_war

    def _analyze_clutch_performance(self, player, event_type, success):
        """
        Stage 8: Analyze and track clutch performance in high-leverage situations.
        """
        # Determine if this is a clutch situation
        is_clutch = (
            self.clock < 120 or  # Final 2 minutes
            abs(self.home_score - self.away_score) <= 1 or  # Close game
            self.current_situation in [SpecialSituation.POWER_PLAY, SpecialSituation.PENALTY_KILL] or
            self.period >= 3  # Third period or overtime
        )
        
        if not is_clutch:
            return
        
        # Calculate leverage factor (how much this situation affects win probability)
        leverage_factor = 1.0
        if self.clock < 60:  # Final minute
            leverage_factor = 2.0
        elif abs(self.home_score - self.away_score) == 0:  # Tied game
            leverage_factor = 1.5
        elif self.period > 3:  # Overtime
            leverage_factor = 3.0
        
        # Track clutch situation
        clutch_event = {
            'player_id': player.id,
            'event_type': event_type,
            'success': success,
            'leverage': leverage_factor,
            'time': self.clock,
            'period': self.period,
            'score_diff': abs(self.home_score - self.away_score)
        }
        
        self.clutch_situations.append(clutch_event)
        
        # Update player clutch stats
        if success:
            self.game_stats[player.id]['clutch_performance'] += leverage_factor
            
            # Update team clutch stats - determine team by checking rosters
            if player in self.home_team.roster:
                team_stats = self.team_stats[self.home_team.team_name]
            else:
                team_stats = self.team_stats[self.away_team.team_name]
            team_stats['clutch_success'] += 1
        
        # Update total clutch moments for team
        if player in self.home_team.roster:
            team_stats = self.team_stats[self.home_team.team_name]
        else:
            team_stats = self.team_stats[self.away_team.team_name]
        team_stats['clutch_moments'] += 1

    def _predict_lineup_optimization(self):
        """
        Stage 8: Use analytics to suggest optimal line combinations.
        """
        optimizations = {}
        
        # Analyze current line performance
        for team in [self.home_team, self.away_team]:
            team_optimizations = {}
            
            # Get current lines (simplified - assuming we track line combinations)
            # In a real implementation, this would analyze actual line performance
            
            # Suggest changes based on:
            # 1. Chemistry ratings
            # 2. Situational performance
            # 3. Fatigue levels
            # 4. Matchup advantages
            
            # For now, create basic optimization suggestions
            team_optimizations['line_changes'] = []
            team_optimizations['special_teams'] = []
            team_optimizations['defensive_pairs'] = []
            
            optimizations[team.team_name] = team_optimizations
        
        self.lineup_analytics = optimizations
        return optimizations

    def _update_performance_trends(self, player):
        """
        Stage 8: Update performance trend analysis for players.
        """
        if player.id not in self.performance_trends:
            return
        
        current_stats = self.game_stats[player.id]
        trends = self.performance_trends[player.id]
        
        # Calculate current game performance score
        performance_score = (current_stats['g'] * 3 + 
                           current_stats['a'] * 2 + 
                           current_stats['shots_on_goal'] * 0.5 +
                           current_stats['takeaways'] * 0.3 -
                           current_stats['giveaways'] * 0.5)
        
        # Add to recent games (in a real implementation, this would be persistent)
        trends['recent_games'].append(performance_score)
        
        # Keep only last few games (simulate game history)
        if len(trends['recent_games']) > 5:
            trends['recent_games'].pop(0)
        
        # Analyze trend direction
        if len(trends['recent_games']) >= 3:
            recent_avg = sum(trends['recent_games'][-3:]) / 3
            older_avg = sum(trends['recent_games'][:-3]) / max(1, len(trends['recent_games']) - 3)
            
            if recent_avg > older_avg * 1.2:
                trends['trend_direction'] = TrendDirection.HOT_STREAK
                trends['hot_streak'] = True
                trends['cold_streak'] = False
            elif recent_avg < older_avg * 0.8:
                trends['trend_direction'] = TrendDirection.COLD_STREAK
                trends['hot_streak'] = False
                trends['cold_streak'] = True
            else:
                trends['trend_direction'] = TrendDirection.STABLE
                trends['hot_streak'] = False
                trends['cold_streak'] = False

    def _generate_analytics_report(self):
        """
        Stage 8: Generate comprehensive analytics report for the game.
        """
        report = {
            'game_summary': {
                'final_score': f"{self.home_score}-{self.away_score}",
                'total_shots': sum(self.team_stats[team]['shots_on_goal'] for team in self.team_stats),
                'total_expected_goals': sum(self.team_stats[team]['expected_goals_for'] for team in self.team_stats),
                'momentum_shifts': len(self.momentum_history),
                'clutch_situations': len(self.clutch_situations)
            },
            'team_analytics': {},
            'player_analytics': {},
            'predictive_accuracy': {},
            'key_insights': []
        }
        
        # Team analytics
        for team_name, stats in self.team_stats.items():
            report['team_analytics'][team_name] = {
                'expected_goals': stats['expected_goals_for'],
                'goals_above_expected': stats['goals_above_expected'],
                'win_probability_final': self.win_probability if team_name == self.home_team.team_name else 1 - self.win_probability,
                'clutch_rating': stats['clutch_rating']
            }
        
        # Top player performances
        top_performers = sorted(
            [(p_id, self.game_stats[p_id]) for p_id in self.game_stats],
            key=lambda x: x[1]['g'] + x[1]['a'] + x[1]['war'],
            reverse=True
        )[:5]
        
        for player_id, stats in top_performers:
            report['player_analytics'][player_id] = {
                'points': stats['g'] + stats['a'],
                'war': stats['war'],
                'expected_goals': stats['expected_goals'],
                'clutch_factor': stats['clutch_factor']
            }
        
        return report

    # ===== STAGE 9: SITUATIONAL AWARENESS & AI METHODS =====

    def _analyze_situational_context(self):
        """
        Stage 9: Analyze current game context and update situational awareness.
        """
        previous_context = self.situational_awareness['current_context']
        
        # Determine current situational context
        new_context = self._determine_situational_context()
        
        # Update context if changed
        if new_context != previous_context:
            self.situational_awareness['context_history'].append({
                'previous': previous_context,
                'new': new_context,
                'time': self.clock,
                'period': self.period,
                'trigger': self._identify_context_trigger(previous_context, new_context)
            })
            
            self.situational_awareness['current_context'] = new_context
            
            # Update stats safely
            home_team_name = self.home_team.team_name
            if home_team_name in self.team_stats and 'situational_context_switches' in self.team_stats[home_team_name]:
                self.team_stats[home_team_name]['situational_context_switches'] += 1
            
            # Trigger AI response to context change
            self._ai_respond_to_context_change(previous_context, new_context)

    def _determine_situational_context(self):
        """
        Stage 9: Determine the current situational context based on game state.
        """
        # Late game situations (last 5 minutes of 3rd period or OT)
        if self.period >= 3 and self.clock <= 300:
            score_diff = self.home_score - self.away_score
            if score_diff == 0:
                return SituationalContext.OVERTIME_SITUATION if self.period > 3 else SituationalContext.CLOSE_GAME_LATE
            elif abs(score_diff) == 1:
                return SituationalContext.TRAILING_LATE if score_diff < 0 else SituationalContext.LEADING_LATE
            elif self.clock <= 120 and abs(score_diff) <= 2:  # Last 2 minutes, within 2 goals
                return SituationalContext.DESPERATION_TIME
        
        # Special teams situations
        if self.current_situation == SpecialSituation.POWER_PLAY:
            return SituationalContext.POWER_PLAY_OPPORTUNITY
        elif self.current_situation == SpecialSituation.PENALTY_KILL:
            return SituationalContext.PENALTY_KILL_SITUATION
        
        # Period boundaries
        if self.clock >= 1140:  # First minute of period
            return SituationalContext.PERIOD_START
        elif self.clock <= 60:  # Last minute of period
            return SituationalContext.PERIOD_END
        
        # Momentum-based contexts
        momentum_index = list(GameMomentum).index(self.momentum)
        if momentum_index <= 1:  # Heavily favoring one team
            return SituationalContext.DOMINANT_PERFORMANCE
        elif abs(momentum_index - 3) >= 2:  # Significant momentum
            return SituationalContext.MOMENTUM_SHIFT
        
        # Default contexts
        if self.period == 1 and self.clock >= 600:  # First half of first period
            return SituationalContext.GAME_OPENING
        
        return SituationalContext.GAME_OPENING  # Default fallback

    def _ai_respond_to_context_change(self, previous_context, new_context):
        """
        Stage 9: AI system responds intelligently to situational context changes.
        """
        # Calculate confidence in context recognition
        confidence = self._calculate_context_confidence(new_context)
        self.situational_awareness['context_confidence'] = confidence
        
        # Determine appropriate AI decision based on context
        decision = self._make_contextual_decision(new_context, confidence)
        
        if decision:
            self._execute_ai_decision(decision, confidence)
            
            # Track decision success for learning
            self.ai_decision_engine['decision_history'].append({
                'context': new_context,
                'decision': decision,
                'confidence': confidence,
                'time': self.clock,
                'period': self.period
            })

    def _make_contextual_decision(self, context, confidence):
        """
        Stage 9: Make intelligent coaching decision based on situational context.
        """
        # Confidence level mapping for comparison
        confidence_levels = {
            AIConfidenceLevel.VERY_LOW: 1,
            AIConfidenceLevel.LOW: 2,
            AIConfidenceLevel.MODERATE: 3,
            AIConfidenceLevel.HIGH: 4,
            AIConfidenceLevel.VERY_HIGH: 5,
            AIConfidenceLevel.CERTAIN: 6
        }
        
        # Only make decisions if confidence is sufficient
        if confidence_levels[confidence] < confidence_levels[AIConfidenceLevel.MODERATE]:
            return None
        
        decisions = []
        
        # Context-specific decision logic
        if context == SituationalContext.TRAILING_LATE:
            if confidence_levels[confidence] >= confidence_levels[AIConfidenceLevel.HIGH]:
                decisions.extend([
                    {'type': AIDecisionType.GOALIE_PULL, 'priority': 0.9},
                    {'type': AIDecisionType.TACTICAL_SHIFT, 'strategy': AdaptiveStrategy.DESPERATION_MODE, 'priority': 0.8},
                    {'type': AIDecisionType.TIMEOUT_CALL, 'priority': 0.7}
                ])
        
        elif context == SituationalContext.LEADING_LATE:
            decisions.extend([
                {'type': AIDecisionType.TACTICAL_SHIFT, 'strategy': AdaptiveStrategy.DEFENSIVE_SHELL, 'priority': 0.8},
                {'type': AIDecisionType.LINE_CHANGE, 'focus': 'defensive', 'priority': 0.7}
            ])
        
        elif context == SituationalContext.POWER_PLAY_OPPORTUNITY:
            decisions.extend([
                {'type': AIDecisionType.SPECIAL_TEAMS_ADJUSTMENT, 'unit': 'power_play', 'priority': 0.9},
                {'type': AIDecisionType.TACTICAL_SHIFT, 'strategy': AdaptiveStrategy.AGGRESSIVE_FORECHECKING, 'priority': 0.6}
            ])
        
        elif context == SituationalContext.MOMENTUM_SHIFT:
            momentum_favors_home = list(GameMomentum).index(self.momentum) < 3
            if momentum_favors_home:
                decisions.append({'type': AIDecisionType.MOMENTUM_RESPONSE, 'action': 'capitalize', 'priority': 0.7})
            else:
                decisions.append({'type': AIDecisionType.MOMENTUM_RESPONSE, 'action': 'counter', 'priority': 0.8})
        
        # Return highest priority decision
        if decisions:
            return max(decisions, key=lambda x: x['priority'])
        
        return None

    def _execute_ai_decision(self, decision, confidence):
        """
        Stage 9: Execute AI coaching decision with confidence-based implementation.
        """
        decision_type = decision['type']
        
        # Adjust execution based on confidence
        execution_strength = self._calculate_execution_strength(confidence)
        
        # Track the decision safely
        home_team_name = self.home_team.team_name
        if home_team_name in self.team_stats and 'ai_decisions_made' in self.team_stats[home_team_name]:
            self.team_stats[home_team_name]['ai_decisions_made'] += 1
        
        # Execute specific decision types
        if decision_type == AIDecisionType.TACTICAL_SHIFT:
            self._execute_tactical_shift(decision.get('strategy'), execution_strength)
        elif decision_type == AIDecisionType.LINE_CHANGE:
            self._execute_intelligent_line_change(decision.get('focus'), execution_strength)
        elif decision_type == AIDecisionType.TIMEOUT_CALL:
            self._execute_strategic_timeout(execution_strength)
        elif decision_type == AIDecisionType.MOMENTUM_RESPONSE:
            self._execute_momentum_response(decision.get('action'), execution_strength)
        
        # Update AI learning based on decision execution
        self._update_ai_learning(decision, execution_strength)

    def _execute_tactical_shift(self, strategy, strength):
        """
        Stage 9: Execute tactical strategy shift with AI-driven adjustments.
        """
        if not strategy:
            return
        
        # Update adaptive strategy
        previous_strategy = self.adaptive_strategy['current_strategy']
        self.adaptive_strategy['current_strategy'] = strategy
        self.adaptive_strategy['strategy_history'].append({
            'from': previous_strategy,
            'to': strategy,
            'strength': strength,
            'time': self.clock
        })
        
        # Apply strategy effects to team performance
        strategy_modifier = self._get_strategy_modifier(strategy, strength)
        
        # Update team stats safely
        home_team_name = self.home_team.team_name
        if home_team_name in self.team_stats:
            if 'adaptive_strategy_changes' in self.team_stats[home_team_name]:
                self.team_stats[home_team_name]['adaptive_strategy_changes'] += 1
            if 'tactical_adaptation_rate' in self.team_stats[home_team_name]:
                self.team_stats[home_team_name]['tactical_adaptation_rate'] += strength

    def _get_strategy_modifier(self, strategy, strength):
        """
        Stage 9: Get performance modifiers for adaptive strategies.
        """
        base_modifiers = {
            AdaptiveStrategy.AGGRESSIVE_FORECHECKING: {'offensive': 1.15, 'defensive': 0.95, 'fatigue': 1.1},
            AdaptiveStrategy.DEFENSIVE_SHELL: {'offensive': 0.85, 'defensive': 1.2, 'fatigue': 0.9},
            AdaptiveStrategy.BALANCED_ATTACK: {'offensive': 1.0, 'defensive': 1.0, 'fatigue': 1.0},
            AdaptiveStrategy.HIGH_TEMPO: {'offensive': 1.1, 'defensive': 0.9, 'fatigue': 1.2},
            AdaptiveStrategy.DESPERATION_MODE: {'offensive': 1.3, 'defensive': 0.7, 'fatigue': 1.3}
        }
        
        modifiers = base_modifiers.get(strategy, {'offensive': 1.0, 'defensive': 1.0, 'fatigue': 1.0})
        
        # Adjust based on execution strength
        for key in modifiers:
            if key != 'fatigue':
                modifiers[key] = 1.0 + (modifiers[key] - 1.0) * strength
        
        return modifiers

    def _update_ai_learning(self, decision, execution_strength):
        """
        Stage 9: Update AI learning patterns based on decision outcomes.
        """
        # Create learning entry
        learning_entry = {
            'decision': decision,
            'execution_strength': execution_strength,
            'context': self.situational_awareness['current_context'],
            'game_state': {
                'score_diff': self.home_score - self.away_score,
                'time_remaining': self.clock + (1200 * (3 - self.period)),
                'momentum': self.momentum,
                'situation': self.current_situation
            },
            'timestamp': self.clock
        }
        
        # Store in learning database
        decision_key = decision['type'].value
        if decision_key not in self.ai_learning['pattern_database']:
            self.ai_learning['pattern_database'][decision_key] = []
        
        self.ai_learning['pattern_database'][decision_key].append(learning_entry)
        
        # Update learning improvements tracker safely
        home_team_name = self.home_team.team_name
        if home_team_name in self.team_stats and 'ai_learning_improvements' in self.team_stats[home_team_name]:
            self.team_stats[home_team_name]['ai_learning_improvements'] += 1

    def _calculate_context_confidence(self, context):
        """
        Stage 9: Calculate AI confidence in situational context recognition.
        """
        base_confidence = AIConfidenceLevel.MODERATE
        
        # Increase confidence for clear-cut situations
        high_confidence_contexts = [
            SituationalContext.POWER_PLAY_OPPORTUNITY,
            SituationalContext.PENALTY_KILL_SITUATION,
            SituationalContext.OVERTIME_SITUATION
        ]
        
        if context in high_confidence_contexts:
            base_confidence = AIConfidenceLevel.HIGH
        
        # Adjust based on game state clarity
        score_diff = abs(self.home_score - self.away_score)
        time_factor = min(self.clock / 1200, 1.0)  # Confidence increases as game progresses
        
        if score_diff >= 3:  # Clear lead
            base_confidence = AIConfidenceLevel.HIGH
        elif score_diff == 0 and self.clock <= 300:  # Tie game, late
            base_confidence = AIConfidenceLevel.VERY_HIGH
        
        return base_confidence

    def _calculate_execution_strength(self, confidence):
        """
        Stage 9: Calculate execution strength based on AI confidence.
        """
        confidence_values = {
            AIConfidenceLevel.VERY_LOW: 0.3,
            AIConfidenceLevel.LOW: 0.5,
            AIConfidenceLevel.MODERATE: 0.7,
            AIConfidenceLevel.HIGH: 0.9,
            AIConfidenceLevel.VERY_HIGH: 1.0,
            AIConfidenceLevel.CERTAIN: 1.0
        }
        
        return confidence_values.get(confidence, 0.7)

    def _identify_context_trigger(self, previous_context, new_context):
        """
        Stage 9: Identify what triggered the context change for learning.
        """
        triggers = {
            (SituationalContext.GAME_OPENING, SituationalContext.POWER_PLAY_OPPORTUNITY): 'penalty_taken',
            (SituationalContext.CLOSE_GAME_LATE, SituationalContext.TRAILING_LATE): 'goal_against',
            (SituationalContext.LEADING_LATE, SituationalContext.CLOSE_GAME_LATE): 'goal_against',
            (SituationalContext.MOMENTUM_SHIFT, SituationalContext.DOMINANT_PERFORMANCE): 'sustained_pressure'
        }
        
        return triggers.get((previous_context, new_context), 'unknown')

    def _execute_intelligent_line_change(self, focus, strength):
        """
        Stage 9: Execute AI-driven intelligent line changes.
        """
        if focus == 'defensive':
            # Prioritize defensive players
            self.team_stats[self.home_team.team_name]['coaching_intervention_success'] += strength * 0.1
        elif focus == 'offensive':
            # Prioritize offensive players
            self.team_stats[self.home_team.team_name]['coaching_intervention_success'] += strength * 0.15
        
        # Force a line change with AI considerations
        self._select_starting_lines()

    def _execute_strategic_timeout(self, strength):
        """
        Stage 9: Execute strategic timeout with AI reasoning.
        """
        # Implement timeout logic (simplified for now)
        self.team_stats[self.home_team.team_name]['intelligent_timeout_usage'] += 1
        
        # Timeout effects: momentum reset, fatigue recovery
        self.momentum = GameMomentum.NEUTRAL
        
        # Restore some fatigue for home team
        for player in self.home_team.roster:
            current_fatigue = self.player_fatigue.get(player.id, 80)
            self.player_fatigue[player.id] = min(100, current_fatigue + (strength * 15))

    def _execute_momentum_response(self, action, strength):
        """
        Stage 9: Execute AI response to momentum shifts.
        """
        home_team_name = self.home_team.team_name
        if action == 'capitalize':
            # Take advantage of positive momentum
            if home_team_name in self.team_stats and 'momentum_response_effectiveness' in self.team_stats[home_team_name]:
                self.team_stats[home_team_name]['momentum_response_effectiveness'] += strength * 0.2
        elif action == 'counter':
            # Counter negative momentum
            if home_team_name in self.team_stats and 'momentum_response_effectiveness' in self.team_stats[home_team_name]:
                self.team_stats[home_team_name]['momentum_response_effectiveness'] += strength * 0.15
            
            # Slight momentum adjustment toward neutral
            current_momentum_index = list(GameMomentum).index(self.momentum)
            if current_momentum_index < 3:  # Favoring away
                new_index = min(current_momentum_index + 1, 6)
                self.momentum = list(GameMomentum)[new_index]

# =============================================================================
# STAGE 9: SITUATIONAL AWARENESS & AI
# =============================================================================

# =============================================================================
# STAGE 9: SITUATIONAL AWARENESS & AI
# =============================================================================

# ===== STAGE 9: SITUATIONAL AWARENESS & AI ENUMS =====

class AIDecisionType(Enum):
    """Types of AI decisions that can be made during gameplay."""
    TIMEOUT_CALL = "timeout_call"
    LINE_CHANGE = "line_change" 
    GOALIE_PULL = "goalie_pull"
    TACTICAL_SHIFT = "tactical_shift"
    SPECIAL_TEAMS_ADJUSTMENT = "special_teams_adjustment"
    DEFENSIVE_STRATEGY = "defensive_strategy"
    OFFENSIVE_STRATEGY = "offensive_strategy"
    MOMENTUM_RESPONSE = "momentum_response"

class SituationalContext(Enum):
    """Contextual game situations that influence AI decision-making."""
    GAME_OPENING = "game_opening"
    PERIOD_START = "period_start"
    PERIOD_END = "period_end"
    MOMENTUM_SHIFT = "momentum_shift"
    POWER_PLAY_OPPORTUNITY = "power_play_opportunity"
    PENALTY_KILL_SITUATION = "penalty_kill_situation"
    CLOSE_GAME_LATE = "close_game_late"
    TRAILING_LATE = "trailing_late"
    LEADING_LATE = "leading_late"
    OVERTIME_SITUATION = "overtime_situation"
    DESPERATION_TIME = "desperation_time"
    DOMINANT_PERFORMANCE = "dominant_performance"

class AIConfidenceLevel(Enum):
    """AI confidence levels for decision-making."""
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CERTAIN = "certain"

class AdaptiveStrategy(Enum):
    """Adaptive strategies the AI can employ."""
    AGGRESSIVE_FORECHECKING = "aggressive_forechecking"
    DEFENSIVE_SHELL = "defensive_shell"
    BALANCED_ATTACK = "balanced_attack"
    HIGH_TEMPO = "high_tempo"
    SLOW_METHODICAL = "slow_methodical"
    SPECIAL_TEAMS_FOCUS = "special_teams_focus"
    MOMENTUM_BUILDING = "momentum_building"
    PRESSURE_RELIEF = "pressure_relief"
    LATE_GAME_MANAGEMENT = "late_game_management"
    DESPERATION_MODE = "desperation_mode"

class AILearningMode(Enum):
    """Learning modes for AI adaptation."""
    PATTERN_RECOGNITION = "pattern_recognition"
    OUTCOME_BASED = "outcome_based"
    SITUATIONAL_LEARNING = "situational_learning"
    OPPONENT_ADAPTATION = "opponent_adaptation"
    REAL_TIME_ADJUSTMENT = "real_time_adjustment"

def simulate_game(home_team: Team, away_team: Team):
    """
    Initializes and runs a GameSim instance, returning the results.
    """
    sim = GameSim(home_team, away_team)
    return sim.run()

# ================================
# STAGE 10: MACHINE LEARNING & PERFORMANCE PREDICTION
# ================================

class MLModelType(Enum):
    """Types of machine learning models for different predictions."""
    PLAYER_DEVELOPMENT = "player_development"
    PERFORMANCE_REGRESSION = "performance_regression"
    INJURY_PREDICTION = "injury_prediction"
    GAME_OUTCOME = "game_outcome"
    SEASON_PROJECTION = "season_projection"
    TRADE_VALUE = "trade_value"
    LINEUP_OPTIMIZATION = "lineup_optimization"

class PredictionAccuracy(Enum):
    """Confidence levels for ML predictions."""
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CERTAIN = "certain"

class DevelopmentPhase(Enum):
    """Player career development phases."""
    PROSPECT = "prospect"
    DEVELOPING = "developing"
    PRIME_EARLY = "prime_early"
    PRIME_PEAK = "prime_peak"
    PRIME_LATE = "prime_late"
    DECLINING = "declining"
    VETERAN = "veteran"

class PerformanceMetric(Enum):
    """Advanced ML performance metrics."""
    EXPECTED_PERFORMANCE = "expected_performance"
    REGRESSION_COEFFICIENT = "regression_coefficient"
    DEVELOPMENT_TRAJECTORY = "development_trajectory"
    INJURY_RISK_FACTOR = "injury_risk_factor"
    CLUTCH_RELIABILITY = "clutch_reliability"
    CONSISTENCY_INDEX = "consistency_index"
    POTENTIAL_REALIZATION = "potential_realization"
    CAREER_VALUE_PROJECTION = "career_value_projection"

class OptimizationTarget(Enum):
    """Optimization targets for ML algorithms."""
    MAXIMIZE_WINS = "maximize_wins"
    MAXIMIZE_GOALS = "maximize_goals"
    MINIMIZE_GOALS_AGAINST = "minimize_goals_against"
    MAXIMIZE_CORSI = "maximize_corsi"
    OPTIMIZE_CHEMISTRY = "optimize_chemistry"
    BALANCE_OFFENSE_DEFENSE = "balance_offense_defense"
    MAXIMIZE_DEVELOPMENT = "maximize_development"
    OPTIMIZE_SALARY_CAP = "optimize_salary_cap"



