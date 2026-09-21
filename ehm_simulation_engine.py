"""
EHM-Style Event-Based Simulation Engine
Phase 2: Sophisticated Decision Chain System
"""

import random
import math
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from dataclasses import dataclass
from enhanced_player_system import EnhancedPlayer, PersonalityType

class GameSituation(Enum):
    EVEN_STRENGTH = "even_strength"
    POWER_PLAY = "power_play"
    PENALTY_KILL = "penalty_kill"
    FOUR_ON_FOUR = "four_on_four"
    THREE_ON_THREE = "three_on_three"
    EMPTY_NET = "empty_net"

class IceZone(Enum):
    DEFENSIVE_ZONE = "defensive_zone"
    NEUTRAL_ZONE = "neutral_zone"
    OFFENSIVE_ZONE = "offensive_zone"

class PuckLocation:
    def __init__(self, x: float, y: float, zone: IceZone):
        self.x = x  # 0-200 (rink length)
        self.y = y  # 0-85 (rink width)
        self.zone = zone

@dataclass
class GameState:
    """Current state of the hockey game"""
    period: int
    time_remaining: int  # seconds
    home_score: int
    away_score: int
    possession_team: str
    puck_location: PuckLocation
    situation: GameSituation
    momentum: float  # -100 to 100, negative favors away team
    last_event_time: int
    
    # Players currently on ice
    home_players_on_ice: List[EnhancedPlayer]
    away_players_on_ice: List[EnhancedPlayer]
    
    # Penalties
    home_penalties: List[Dict]  # {'player': player, 'time_remaining': seconds, 'type': str}
    away_penalties: List[Dict]

class ActionType(Enum):
    PASS = "pass"
    SHOOT = "shoot"
    DEKE = "deke"
    CHECK = "check"
    BLOCK_SHOT = "block_shot"
    CLEAR = "clear"
    SKATE = "skate"
    FACEOFF = "faceoff"
    SAVE = "save"
    REBOUND = "rebound"

@dataclass
class GameAction:
    """Represents a single action in the game"""
    action_type: ActionType
    primary_player: EnhancedPlayer
    target_player: Optional[EnhancedPlayer]
    location: PuckLocation
    success: bool
    description: str
    consequences: List[str]

class EHMSimulationEngine:
    """EHM-style simulation engine with deep decision-making"""
    
    def __init__(self, home_team: str, away_team: str, home_roster: List[EnhancedPlayer], away_roster: List[EnhancedPlayer]):
        self.home_team = home_team
        self.away_team = away_team
        self.home_roster = home_roster
        self.away_roster = away_roster
        
        # Game state
        self.game_state = GameState(
            period=1,
            time_remaining=1200,  # 20 minutes
            home_score=0,
            away_score=0,
            possession_team=home_team,
            puck_location=PuckLocation(100, 42.5, IceZone.NEUTRAL_ZONE),
            situation=GameSituation.EVEN_STRENGTH,
            momentum=0.0,
            last_event_time=0,
            home_players_on_ice=[],
            away_players_on_ice=[],
            home_penalties=[],
            away_penalties=[]
        )
        
        # Event log for detailed tracking
        self.event_log = []
        self.detailed_log = []
        
        # Performance tracking
        self.player_performance = {}
        
        # Initialize starting lineups
        self._set_starting_lineups()
    
    def _set_starting_lineups(self):
        """Set starting lineups for both teams"""
        # Get best players for each position
        home_forwards = [p for p in self.home_roster if p.primary_position.value in ['C', 'LW', 'RW']]
        home_defense = [p for p in self.home_roster if p.primary_position.value in ['LD', 'RD', 'D']]
        home_goalies = [p for p in self.home_roster if p.primary_position.value == 'G']
        
        away_forwards = [p for p in self.away_roster if p.primary_position.value in ['C', 'LW', 'RW']]
        away_defense = [p for p in self.away_roster if p.primary_position.value in ['LD', 'RD', 'D']]
        away_goalies = [p for p in self.away_roster if p.primary_position.value == 'G']
        
        # Sort by overall rating and take top players
        home_forwards.sort(key=lambda x: x.overall_rating(), reverse=True)
        home_defense.sort(key=lambda x: x.overall_rating(), reverse=True)
        away_forwards.sort(key=lambda x: x.overall_rating(), reverse=True)
        away_defense.sort(key=lambda x: x.overall_rating(), reverse=True)
        
        # Starting lineups: 3F, 2D, 1G
        self.game_state.home_players_on_ice = (
            home_forwards[:3] + home_defense[:2] + home_goalies[:1]
        )
        self.game_state.away_players_on_ice = (
            away_forwards[:3] + away_defense[:2] + away_goalies[:1]
        )
    
    def simulate_next_event(self) -> Optional[GameAction]:
        """Simulate the next event in the game using EHM-style decision chains"""
        
        # Update game time
        time_advance = random.uniform(3, 15)  # 3-15 seconds between events
        
        # Ensure time doesn't go negative
        if time_advance > self.game_state.time_remaining:
            time_advance = self.game_state.time_remaining
        
        self.game_state.time_remaining -= time_advance
        
        if self.game_state.time_remaining <= 0:
            self.game_state.time_remaining = 0  # Ensure exactly 0, not negative
            return self._handle_period_end()
        
        # Get puck carrier
        possessing_team_players = (self.game_state.home_players_on_ice 
                                 if self.game_state.possession_team == self.home_team 
                                 else self.game_state.away_players_on_ice)
        
        if not possessing_team_players:
            return None
        
        # Select puck carrier based on situation and position
        puck_carrier = self._select_puck_carrier(possessing_team_players)
        
        # Create situation context
        situation_context = self._build_situation_context(puck_carrier)
        
        # Decision Layer 1: Situational Assessment
        assessment = self._assess_situation(puck_carrier, situation_context)
        
        # Decision Layer 2: Action Selection
        available_actions = self._get_available_actions(puck_carrier, assessment)
        chosen_action = puck_carrier.make_decision(available_actions, situation_context)
        
        # Decision Layer 3: Execution and Resolution
        game_action = self._execute_action(puck_carrier, chosen_action, situation_context)
        
        # Update game state based on action result
        self._update_game_state(game_action)
        
        # Log the event
        self.event_log.append(game_action)
        self._update_detailed_log(game_action)
        
        return game_action
    
    def _select_puck_carrier(self, team_players: List[EnhancedPlayer]) -> EnhancedPlayer:
        """Select which player has the puck based on situation and positioning"""
        # Weight players based on position and current zone
        weights = []
        
        for player in team_players:
            base_weight = 1.0
            
            # Forwards more likely to carry puck in offensive zone
            if (self.game_state.puck_location.zone == IceZone.OFFENSIVE_ZONE and 
                player.primary_position.value in ['C', 'LW', 'RW']):
                base_weight *= 2.0
            
            # Defensemen more likely in defensive zone
            elif (self.game_state.puck_location.zone == IceZone.DEFENSIVE_ZONE and 
                  player.primary_position.value in ['LD', 'RD', 'D']):
                base_weight *= 2.5
            
            # Centers often carry puck in neutral zone
            elif (self.game_state.puck_location.zone == IceZone.NEUTRAL_ZONE and 
                  player.primary_position.value == 'C'):
                base_weight *= 1.8
            
            # Factor in player attributes
            base_weight *= (player.stickhandling + player.offensive_read) / 30
            
            weights.append((player, base_weight))
        
        # Weighted random selection
        return self._weighted_random_choice_from_list(weights)
    
    def _build_situation_context(self, puck_carrier: EnhancedPlayer) -> Dict[str, Any]:
        """Build comprehensive situation context for decision making"""
        score_diff = self.game_state.home_score - self.game_state.away_score
        if self.game_state.possession_team == self.away_team:
            score_diff = -score_diff
        
        # Determine pressure level
        pressure_level = 0
        if self.game_state.time_remaining < 300:  # Last 5 minutes
            pressure_level += 3
        if abs(score_diff) <= 1:  # Close game
            pressure_level += 2
        if self.game_state.period == 3:  # Third period
            pressure_level += 2
        
        opposing_players = (self.game_state.away_players_on_ice 
                          if self.game_state.possession_team == self.home_team 
                          else self.game_state.home_players_on_ice)
        
        # Check for open teammates
        teammates_open = random.random() < 0.6  # Simplified for now
        
        return {
            'score_differential': score_diff,
            'time_remaining': self.game_state.time_remaining,
            'period': self.game_state.period,
            'pressure_level': pressure_level,
            'is_clutch_time': self.game_state.time_remaining < 120 and abs(score_diff) <= 1,
            'zone': self.game_state.puck_location.zone,
            'situation': self.game_state.situation,
            'teammates_open': teammates_open,
            'momentum': self.game_state.momentum,
            'opposing_pressure': len(opposing_players) >= 5  # Full strength check
        }
    
    def _assess_situation(self, player: EnhancedPlayer, context: Dict[str, Any]) -> Dict[str, float]:
        """Player assesses the situation using their hockey IQ"""
        assessment = {}
        
        # Base assessment modified by player's read attributes
        read_modifier = (player.offensive_read + player.defensive_read) / 40
        
        # Assess shooting opportunity
        if context['zone'] == IceZone.OFFENSIVE_ZONE:
            base_shot_quality = 0.7
            assessment['shot_quality'] = base_shot_quality * read_modifier
        else:
            assessment['shot_quality'] = 0.1
        
        # Assess passing opportunities
        if context['teammates_open']:
            base_pass_quality = 0.8
            assessment['pass_quality'] = base_pass_quality * read_modifier
        else:
            assessment['pass_quality'] = 0.4
        
        # Assess defensive pressure
        if context['opposing_pressure']:
            assessment['pressure_level'] = 0.8
        else:
            assessment['pressure_level'] = 0.3
        
        # Risk assessment
        if context['is_clutch_time']:
            assessment['risk_tolerance'] = 0.3  # More conservative in clutch time
        else:
            assessment['risk_tolerance'] = 0.6
        
        return assessment
    
    def _get_available_actions(self, player: EnhancedPlayer, assessment: Dict[str, float]) -> List[str]:
        """Get list of available actions based on situation"""
        actions = ['pass', 'skate']  # Always available
        
        # Zone-based actions
        if self.game_state.puck_location.zone == IceZone.OFFENSIVE_ZONE:
            actions.extend(['shoot', 'deke'])
        
        if self.game_state.puck_location.zone == IceZone.DEFENSIVE_ZONE:
            actions.extend(['clear'])
        
        # Position-based actions
        if player.primary_position.value in ['LD', 'RD', 'D']:
            actions.append('clear')
        
        # Situation-based actions
        if assessment['pressure_level'] > 0.6:
            actions.append('check')
        
        return actions
    
    def _execute_action(self, player: EnhancedPlayer, action: str, context: Dict[str, Any]) -> GameAction:
        """Execute the chosen action and determine its outcome"""
        
        # Get performance modifier for this player in this situation
        performance_mod = player.get_performance_modifier(context)
        
        if action == 'shoot':
            return self._execute_shot(player, context, performance_mod)
        elif action == 'pass':
            return self._execute_pass(player, context, performance_mod)
        elif action == 'deke':
            return self._execute_deke(player, context, performance_mod)
        elif action == 'check':
            return self._execute_check(player, context, performance_mod)
        elif action == 'clear':
            return self._execute_clear(player, context, performance_mod)
        elif action == 'skate':
            return self._execute_skate(player, context, performance_mod)
        else:
            # Default action
            return GameAction(
                action_type=ActionType.SKATE,
                primary_player=player,
                target_player=None,
                location=self.game_state.puck_location,
                success=True,
                description=f"{player.full_name} skates with the puck",
                consequences=[]
            )
    
    def _execute_shot(self, shooter: EnhancedPlayer, context: Dict[str, Any], performance_mod: float) -> GameAction:
        """Execute a shot attempt with realistic outcome determination"""
        
        # Get opposing goalie
        opposing_players = (self.game_state.away_players_on_ice 
                          if self.game_state.possession_team == self.home_team 
                          else self.game_state.home_players_on_ice)
        
        goalie = next((p for p in opposing_players if p.primary_position.value == 'G'), None)
        
        # Calculate shot skill
        shot_skill = (
            shooter.shooting_accuracy * 0.4 +
            shooter.shooting_power * 0.3 +
            shooter.offensive_read * 0.2 +
            shooter.clutch_factor * 0.1
        ) * performance_mod
        
        # Calculate save skill
        if goalie:
            goalie_performance = goalie.get_performance_modifier(context)
            save_skill = (
                goalie.reflexes * 0.3 +
                goalie.positioning * 0.3 +
                goalie.rebound_control * 0.2 +
                goalie.mental_toughness * 0.2
            ) * goalie_performance
        else:
            save_skill = 10  # Emergency goalie
        
        # Determine outcome
        shot_quality = random.uniform(0.7, 1.3)  # Shot quality randomness
        final_shot_value = shot_skill * shot_quality
        final_save_value = save_skill * random.uniform(0.8, 1.2)
        
        # Goal probability calculation
        goal_probability = max(0.05, min(0.35, (final_shot_value - final_save_value) / 100))
        
        if random.random() < goal_probability:
            # GOAL!
            if self.game_state.possession_team == self.home_team:
                self.game_state.home_score += 1
            else:
                self.game_state.away_score += 1
            
            # Update momentum
            self.game_state.momentum += 15 if self.game_state.possession_team == self.home_team else -15
            
            # Update player stats and morale
            shooter.season_goals += 1
            shooter.update_morale('goal_scored')
            
            return GameAction(
                action_type=ActionType.SHOOT,
                primary_player=shooter,
                target_player=goalie,
                location=self.game_state.puck_location,
                success=True,
                description=f"GOAL! {shooter.full_name} scores! {self.home_team} {self.game_state.home_score} - {self.away_team} {self.game_state.away_score}",
                consequences=['goal_scored', 'momentum_shift']
            )
        else:
            # Save or miss
            if goalie and final_save_value > final_shot_value * 0.8:
                description = f"Shot by {shooter.full_name} - SAVE by {goalie.full_name}!"
            else:
                description = f"Shot by {shooter.full_name} goes wide!"
            
            # Possession change
            self._change_possession()
            
            return GameAction(
                action_type=ActionType.SHOOT,
                primary_player=shooter,
                target_player=goalie,
                location=self.game_state.puck_location,
                success=False,
                description=description,
                consequences=['possession_change']
            )
    
    def _execute_pass(self, passer: EnhancedPlayer, context: Dict[str, Any], performance_mod: float) -> GameAction:
        """Execute a pass attempt"""
        
        # Get teammates
        team_players = (self.game_state.home_players_on_ice 
                       if self.game_state.possession_team == self.home_team 
                       else self.game_state.away_players_on_ice)
        
        potential_targets = [p for p in team_players if p != passer and p.primary_position.value != 'G']
        
        if not potential_targets:
            return self._execute_skate(passer, context, performance_mod)
        
        # Select pass target
        target = random.choice(potential_targets)
        
        # Calculate pass success
        pass_skill = (
            passer.passing_accuracy * 0.4 +
            passer.passing_vision * 0.3 +
            passer.offensive_read * 0.2 +
            passer.anticipation * 0.1
        ) * performance_mod
        
        # Factor in chemistry
        chemistry_bonus = passer.line_chemistry.get(target.full_name, 50) / 100
        pass_skill *= (0.8 + chemistry_bonus * 0.4)
        
        # Defensive pressure
        opposing_pressure = context.get('opposing_pressure', False)
        if opposing_pressure:
            pass_skill *= 0.75
        
        success_chance = min(0.95, pass_skill / 100)
        
        if random.random() < success_chance:
            # Successful pass
            passer.update_chemistry(target.full_name, True)
            
            return GameAction(
                action_type=ActionType.PASS,
                primary_player=passer,
                target_player=target,
                location=self.game_state.puck_location,
                success=True,
                description=f"{passer.full_name} passes to {target.full_name}",
                consequences=['chemistry_boost']
            )
        else:
            # Failed pass - turnover
            passer.update_chemistry(target.full_name, False)
            self._change_possession()
            
            return GameAction(
                action_type=ActionType.PASS,
                primary_player=passer,
                target_player=target,
                location=self.game_state.puck_location,
                success=False,
                description=f"{passer.full_name}'s pass to {target.full_name} is intercepted!",
                consequences=['turnover', 'possession_change']
            )
    
    def _execute_deke(self, player: EnhancedPlayer, context: Dict[str, Any], performance_mod: float) -> GameAction:
        """Execute a deke/stickhandling move"""
        
        deke_skill = (
            player.stickhandling * 0.5 +
            player.skating_agility * 0.3 +
            player.offensive_read * 0.2
        ) * performance_mod
        
        success_chance = min(0.7, deke_skill / 100)
        
        if random.random() < success_chance:
            # Successful deke
            return GameAction(
                action_type=ActionType.DEKE,
                primary_player=player,
                target_player=None,
                location=self.game_state.puck_location,
                success=True,
                description=f"{player.full_name} dekes around the defender!",
                consequences=['scoring_chance_created']
            )
        else:
            # Failed deke
            self._change_possession()
            return GameAction(
                action_type=ActionType.DEKE,
                primary_player=player,
                target_player=None,
                location=self.game_state.puck_location,
                success=False,
                description=f"{player.full_name} loses the puck trying to deke!",
                consequences=['turnover', 'possession_change']
            )
    
    def _execute_check(self, checker: EnhancedPlayer, context: Dict[str, Any], performance_mod: float) -> GameAction:
        """Execute a body check"""
        
        # Get random opposing player
        opposing_players = (self.game_state.away_players_on_ice 
                          if self.game_state.possession_team == self.away_team 
                          else self.game_state.home_players_on_ice)
        
        target = random.choice([p for p in opposing_players if p.primary_position.value != 'G'])
        
        check_skill = (
            checker.body_checking * 0.4 +
            checker.strength * 0.3 +
            checker.aggression * 0.2 +
            checker.anticipation * 0.1
        ) * performance_mod
        
        if random.random() < check_skill / 100:
            # Successful check
            self._change_possession()
            
            return GameAction(
                action_type=ActionType.CHECK,
                primary_player=checker,
                target_player=target,
                location=self.game_state.puck_location,
                success=True,
                description=f"{checker.full_name} delivers a big hit on {target.full_name}!",
                consequences=['momentum_shift', 'possession_change']
            )
        else:
            # Missed check
            return GameAction(
                action_type=ActionType.CHECK,
                primary_player=checker,
                target_player=target,
                location=self.game_state.puck_location,
                success=False,
                description=f"{checker.full_name} misses the check on {target.full_name}",
                consequences=[]
            )
    
    def _execute_clear(self, player: EnhancedPlayer, context: Dict[str, Any], performance_mod: float) -> GameAction:
        """Execute a clearing attempt"""
        
        clear_skill = (
            player.passing_accuracy * 0.4 +
            player.strength * 0.3 +
            player.defensive_read * 0.3
        ) * performance_mod
        
        if random.random() < clear_skill / 100:
            # Successful clear
            self._change_possession()
            self.game_state.puck_location.zone = IceZone.NEUTRAL_ZONE
            
            return GameAction(
                action_type=ActionType.CLEAR,
                primary_player=player,
                target_player=None,
                location=self.game_state.puck_location,
                success=True,
                description=f"{player.full_name} clears the puck out of the zone",
                consequences=['zone_change', 'possession_change']
            )
        else:
            # Failed clear
            return GameAction(
                action_type=ActionType.CLEAR,
                primary_player=player,
                target_player=None,
                location=self.game_state.puck_location,
                success=False,
                description=f"{player.full_name}'s clearing attempt is blocked",
                consequences=[]
            )
    
    def _execute_skate(self, player: EnhancedPlayer, context: Dict[str, Any], performance_mod: float) -> GameAction:
        """Execute skating with the puck"""
        
        return GameAction(
            action_type=ActionType.SKATE,
            primary_player=player,
            target_player=None,
            location=self.game_state.puck_location,
            success=True,
            description=f"{player.full_name} skates with the puck",
            consequences=[]
        )
    
    def _change_possession(self):
        """Change possession to the other team"""
        self.game_state.possession_team = (self.away_team 
                                         if self.game_state.possession_team == self.home_team 
                                         else self.home_team)
    
    def _update_game_state(self, action: GameAction):
        """Update game state based on the action result"""
        
        # Update momentum based on action
        if 'momentum_shift' in action.consequences:
            momentum_change = 5 if action.success else -5
            if self.game_state.possession_team == self.away_team:
                momentum_change = -momentum_change
            self.game_state.momentum += momentum_change
            self.game_state.momentum = max(-100, min(100, self.game_state.momentum))
        
        # Update zone based on action
        if 'zone_change' in action.consequences:
            # Simplified zone transitions
            current_zone = self.game_state.puck_location.zone
            if current_zone == IceZone.DEFENSIVE_ZONE:
                self.game_state.puck_location.zone = IceZone.NEUTRAL_ZONE
            elif current_zone == IceZone.NEUTRAL_ZONE:
                self.game_state.puck_location.zone = (IceZone.OFFENSIVE_ZONE 
                                                     if random.random() < 0.6 
                                                     else IceZone.DEFENSIVE_ZONE)
    
    def _update_detailed_log(self, action: GameAction):
        """Update detailed event log for replay purposes"""
        log_entry = {
            'timestamp': 1200 - self.game_state.time_remaining,
            'period': self.game_state.period,
            'time': self._format_time(self.game_state.time_remaining),
            'action': action.action_type.value,
            'primary_player': action.primary_player.full_name,
            'target_player': action.target_player.full_name if action.target_player else None,
            'description': action.description,
            'success': action.success,
            'location': {
                'x': action.location.x,
                'y': action.location.y,
                'zone': action.location.zone.value
            },
            'game_state': {
                'home_score': self.game_state.home_score,
                'away_score': self.game_state.away_score,
                'possession': self.game_state.possession_team,
                'momentum': self.game_state.momentum
            }
        }
        
        self.detailed_log.append(log_entry)
    
    def _handle_period_end(self) -> GameAction:
        """Handle end of period"""
        if self.game_state.period < 3:
            self.game_state.period += 1
            self.game_state.time_remaining = 1200
            
            return GameAction(
                action_type=ActionType.SKATE,  # Placeholder
                primary_player=self.game_state.home_players_on_ice[0],
                target_player=None,
                location=self.game_state.puck_location,
                success=True,
                description=f"End of Period {self.game_state.period - 1}",
                consequences=['period_end']
            )
        else:
            return GameAction(
                action_type=ActionType.SKATE,  # Placeholder
                primary_player=self.game_state.home_players_on_ice[0],
                target_player=None,
                location=self.game_state.puck_location,
                success=True,
                description=f"Game Over: {self.home_team} {self.game_state.home_score} - {self.away_team} {self.game_state.away_score}",
                consequences=['game_end']
            )
    
    def _format_time(self, seconds: float) -> str:
        """Format time as MM:SS"""
        seconds = int(seconds)  # Convert to int for formatting
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"
    
    def _weighted_random_choice(self, weights: Dict[Any, float]) -> Any:
        """Select item based on weights (for dictionaries)"""
        total = sum(weights.values())
        rand_val = random.random() * total
        
        cumulative = 0
        for item, weight in weights.items():
            cumulative += weight
            if rand_val <= cumulative:
                return item
        
        return list(weights.keys())[0]  # Fallback
    
    def _weighted_random_choice_from_list(self, weighted_items: List[Tuple[Any, float]]) -> Any:
        """Select item based on weights (for lists of tuples)"""
        total = sum(weight for _, weight in weighted_items)
        rand_val = random.random() * total
        
        cumulative = 0
        for item, weight in weighted_items:
            cumulative += weight
            if rand_val <= cumulative:
                return item
        
        return weighted_items[0][0] if weighted_items else None  # Fallback
    
    def simulate_game(self) -> Dict[str, Any]:
        """Simulate a complete game"""
        while self.game_state.period <= 3 and self.game_state.time_remaining > 0:
            action = self.simulate_next_event()
            if not action:
                break
            
            if 'game_end' in action.consequences:
                break
        
        return {
            'home_team': self.home_team,
            'away_team': self.away_team,
            'home_score': self.game_state.home_score,
            'away_score': self.game_state.away_score,
            'events': self.event_log,
            'detailed_log': self.detailed_log,
            'final_momentum': self.game_state.momentum
        }
