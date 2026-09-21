"""
NHL Coordinate-Based Simulation Engine
Integrates realistic ice coordinates with danger zone analytics
"""

import random
import math
from enum import Enum
from typing import Tuple, Dict, List, Optional

class IceZone(Enum):
    """NHL regulation rink zones with coordinate boundaries"""
    HOME_ZONE = "home_zone"           # 0-66 feet
    NEUTRAL_ZONE = "neutral_zone"     # 67-133 feet  
    AWAY_ZONE = "away_zone"           # 134-200 feet
    HOME_CREASE = "home_crease"       # Special zone around home goal
    AWAY_CREASE = "away_crease"       # Special zone around away goal

class DangerLevel(Enum):
    """Shot danger levels based on coordinate analysis"""
    VERY_HIGH = "very_high"    # Crease, slot from close range
    HIGH = "high"              # High slot, faceoff circles
    MEDIUM = "medium"          # Wing areas, point shots
    LOW = "low"                # Long distance, bad angles

class CoordinateSimEngine:
    """Enhanced simulation engine with NHL regulation coordinates"""
    
    def __init__(self):
        # NHL regulation rink: 200 feet long x 85 feet wide
        self.RINK_LENGTH = 200
        self.RINK_WIDTH = 85
        
        # Goal line positions
        self.HOME_GOAL_LINE = 11   # 11 feet from end boards
        self.AWAY_GOAL_LINE = 189  # 189 feet from home end
        
        # Zone boundaries
        self.HOME_BLUE_LINE = 67
        self.AWAY_BLUE_LINE = 133
        
        # Center line
        self.CENTER_LINE = 100
        
        # Critical scoring areas (high danger zones)
        self.HIGH_DANGER_ZONES = self._define_high_danger_zones()
        
        # Player position tracking
        self.player_positions = {}  # player_id -> (x, y)
        self.puck_position = (100, 42.5)  # Start at center ice
        
        # Zone transition tracking
        self.zone_entries = []
        self.shot_locations = []

    def _define_high_danger_zones(self) -> List[Dict]:
        """Define high-danger scoring areas based on NHL analytics"""
        return [
            # Home high-danger areas
            {
                'name': 'home_crease',
                'zone': IceZone.HOME_ZONE,
                'x_min': 6, 'x_max': 16,
                'y_min': 37, 'y_max': 48,
                'danger_level': DangerLevel.VERY_HIGH,
                'goal_multiplier': 3.5
            },
            {
                'name': 'home_slot',
                'zone': IceZone.HOME_ZONE,
                'x_min': 16, 'x_max': 35,
                'y_min': 32, 'y_max': 53,
                'danger_level': DangerLevel.HIGH,
                'goal_multiplier': 2.2
            },
            {
                'name': 'home_high_slot',
                'zone': IceZone.HOME_ZONE,
                'x_min': 35, 'x_max': 55,
                'y_min': 25, 'y_max': 60,
                'danger_level': DangerLevel.MEDIUM,
                'goal_multiplier': 1.4
            },
            
            # Away high-danger areas (mirrored)
            {
                'name': 'away_crease',
                'zone': IceZone.AWAY_ZONE,
                'x_min': 184, 'x_max': 194,
                'y_min': 37, 'y_max': 48,
                'danger_level': DangerLevel.VERY_HIGH,
                'goal_multiplier': 3.5
            },
            {
                'name': 'away_slot',
                'zone': IceZone.AWAY_ZONE,
                'x_min': 165, 'x_max': 184,
                'y_min': 32, 'y_max': 53,
                'danger_level': DangerLevel.HIGH,
                'goal_multiplier': 2.2
            },
            {
                'name': 'away_high_slot',
                'zone': IceZone.AWAY_ZONE,
                'x_min': 145, 'x_max': 165,
                'y_min': 25, 'y_max': 60,
                'danger_level': DangerLevel.MEDIUM,
                'goal_multiplier': 1.4
            }
        ]

    def initialize_player_positions(self, home_players: List, away_players: List):
        """Set initial player positions for game start"""
        # Home team defensive positions
        for i, player in enumerate(home_players[:6]):  # 6 skaters
            if i < 3:  # Forwards
                x = random.randint(45, 65)
                y = 20 + (i * 15) + random.randint(-5, 5)
            else:  # Defense
                x = random.randint(25, 45)
                y = 25 + ((i-3) * 20) + random.randint(-3, 3)
            
            self.player_positions[player.id] = (x, y)
        
        # Away team offensive positions  
        for i, player in enumerate(away_players[:6]):  # 6 skaters
            if i < 3:  # Forwards
                x = random.randint(135, 155)
                y = 20 + (i * 15) + random.randint(-5, 5)
            else:  # Defense
                x = random.randint(155, 175)
                y = 25 + ((i-3) * 20) + random.randint(-3, 3)
            
            self.player_positions[player.id] = (x, y)
        
        # Goalies
        home_goalies = [p for p in home_players if hasattr(p, 'primary_position') and 'GOALIE' in str(p.primary_position)]
        away_goalies = [p for p in away_players if hasattr(p, 'primary_position') and 'GOALIE' in str(p.primary_position)]
        
        if home_goalies:
            self.player_positions[home_goalies[0].id] = (self.HOME_GOAL_LINE, 42.5)
        if away_goalies:
            self.player_positions[away_goalies[0].id] = (self.AWAY_GOAL_LINE, 42.5)

    def get_zone_from_coordinates(self, x: float, y: float) -> IceZone:
        """Determine ice zone from coordinates"""
        if x <= self.HOME_BLUE_LINE:
            return IceZone.HOME_ZONE
        elif x >= self.AWAY_BLUE_LINE:
            return IceZone.AWAY_ZONE
        else:
            return IceZone.NEUTRAL_ZONE

    def get_danger_level(self, x: float, y: float, attacking_home_goal: bool = False) -> Tuple[DangerLevel, float]:
        """
        Analyze shot danger level based on coordinates
        Returns (danger_level, goal_probability_multiplier)
        """
        # Determine which zones to check based on attack direction
        relevant_zones = []
        
        if attacking_home_goal:
            # Attacking home goal (away team shooting)
            relevant_zones = [zone for zone in self.HIGH_DANGER_ZONES if 'home' in zone['name']]
        else:
            # Attacking away goal (home team shooting)  
            relevant_zones = [zone for zone in self.HIGH_DANGER_ZONES if 'away' in zone['name']]
        
        # Check if shot location is in any high-danger zone
        for zone in relevant_zones:
            if (zone['x_min'] <= x <= zone['x_max'] and 
                zone['y_min'] <= y <= zone['y_max']):
                return zone['danger_level'], zone['goal_multiplier']
        
        # Calculate distance-based danger for non-zone shots
        goal_x = self.HOME_GOAL_LINE if attacking_home_goal else self.AWAY_GOAL_LINE
        goal_y = 42.5
        
        distance = math.sqrt((x - goal_x)**2 + (y - goal_y)**2)
        angle = self._calculate_shot_angle(x, y, goal_x, goal_y)
        
        # Distance and angle based danger
        if distance <= 15 and angle >= 30:
            return DangerLevel.HIGH, 2.0
        elif distance <= 25 and angle >= 20:
            return DangerLevel.MEDIUM, 1.5
        elif distance <= 40 and angle >= 10:
            return DangerLevel.MEDIUM, 1.2
        else:
            return DangerLevel.LOW, 0.8

    def _calculate_shot_angle(self, shot_x: float, shot_y: float, goal_x: float, goal_y: float) -> float:
        """Calculate shooting angle in degrees"""
        # Goal posts are 6 feet apart (3 feet each side of center)
        left_post_y = goal_y - 3
        right_post_y = goal_y + 3
        
        # Calculate angles to each post
        angle_left = math.degrees(math.atan2(abs(shot_y - left_post_y), abs(shot_x - goal_x)))
        angle_right = math.degrees(math.atan2(abs(shot_y - right_post_y), abs(shot_x - goal_x)))
        
        # Return the shooting angle (angle between the two post lines)
        return abs(angle_left - angle_right)

    def generate_shot_coordinates(self, shooter_position: Tuple[float, float], 
                                 attacking_home_goal: bool = False) -> Dict:
        """Generate realistic shot coordinates and analyze danger"""
        shot_x, shot_y = shooter_position
        
        # Add some variation to shot position (player movement)
        shot_x += random.uniform(-2, 2)
        shot_y += random.uniform(-2, 2)
        
        # Ensure shot is within rink bounds
        shot_x = max(0, min(self.RINK_LENGTH, shot_x))
        shot_y = max(0, min(self.RINK_WIDTH, shot_y))
        
        # Determine target coordinates (where shot is aimed)
        goal_x = self.HOME_GOAL_LINE if attacking_home_goal else self.AWAY_GOAL_LINE
        goal_y = 42.5  # Center of goal
        
        # Add accuracy variation (better players more accurate)
        target_variation = random.uniform(-3, 3)  # ±3 feet accuracy variation
        target_x = goal_x
        target_y = goal_y + target_variation
        
        # Get danger analysis
        danger_level, multiplier = self.get_danger_level(shot_x, shot_y, attacking_home_goal)
        
        # Calculate expected goal probability
        distance = math.sqrt((shot_x - goal_x)**2 + (shot_y - goal_y)**2)
        angle = self._calculate_shot_angle(shot_x, shot_y, goal_x, goal_y)
        
        # Base expected goal calculation
        base_xg = max(0.01, min(0.50, (50 - distance) / 100 * (angle / 180)))
        expected_goal = base_xg * multiplier
        
        return {
            'shot_position': (shot_x, shot_y),
            'target_position': (target_x, target_y),
            'distance': distance,
            'angle': angle,
            'danger_level': danger_level,
            'expected_goal': expected_goal,
            'zone': self.get_zone_from_coordinates(shot_x, shot_y),
            'attacking_home_goal': attacking_home_goal
        }

    def simulate_player_movement(self, player_id: str, target_position: Tuple[float, float], 
                               movement_type: str = "skate") -> List[Dict]:
        """Generate realistic player movement events with coordinates"""
        if player_id not in self.player_positions:
            return []
        
        start_x, start_y = self.player_positions[player_id]
        target_x, target_y = target_position
        
        # Calculate movement distance and time
        distance = math.sqrt((target_x - start_x)**2 + (target_y - start_y)**2)
        
        # Movement speed based on type
        speeds = {
            'skate': 15,      # feet per second
            'sprint': 25,     # feet per second  
            'backskate': 10,  # feet per second
            'glide': 8        # feet per second
        }
        
        speed = speeds.get(movement_type, 15)
        duration = distance / speed
        
        # Generate movement waypoints for smooth animation
        movement_events = []
        steps = max(3, int(distance / 5))  # One waypoint every 5 feet
        
        for i in range(steps + 1):
            progress = i / steps
            
            # Linear interpolation with slight curve for realism
            curve_factor = math.sin(progress * math.pi) * 0.1
            current_x = start_x + (target_x - start_x) * progress
            current_y = start_y + (target_y - start_y) * progress + curve_factor
            
            # Ensure within rink bounds
            current_x = max(0, min(self.RINK_LENGTH, current_x))
            current_y = max(0, min(self.RINK_WIDTH, current_y))
            
            timestamp = (duration / steps) * i
            
            movement_events.append({
                'timestamp': timestamp,
                'duration': duration / steps,
                'type': 'PLAYER_MOVEMENT',
                'details': {
                    'player_id': player_id,
                    'position': (current_x, current_y),
                    'movement_type': movement_type,
                    'progress': progress
                }
            })
        
        # Update final position
        self.player_positions[player_id] = (target_x, target_y)
        
        return movement_events

    def simulate_puck_movement(self, start_pos: Tuple[float, float], 
                              end_pos: Tuple[float, float], 
                              movement_type: str = "pass") -> List[Dict]:
        """Generate realistic puck movement with physics"""
        start_x, start_y = start_pos
        end_x, end_y = end_pos
        
        distance = math.sqrt((end_x - start_x)**2 + (end_y - start_y)**2)
        
        # Puck speeds
        speeds = {
            'pass': 40,        # feet per second
            'shot': 80,        # feet per second
            'dump': 30,        # feet per second
            'clear': 50        # feet per second
        }
        
        speed = speeds.get(movement_type, 40)
        duration = distance / speed
        
        # Generate puck trajectory
        puck_events = []
        steps = max(2, int(distance / 10))  # Waypoint every 10 feet
        
        for i in range(steps + 1):
            progress = i / steps
            
            # Add physics curve for shots (arc trajectory)
            if movement_type == 'shot' and distance > 20:
                arc_height = math.sin(progress * math.pi) * 2  # 2 foot arc
                current_x = start_x + (end_x - start_x) * progress
                current_y = start_y + (end_y - start_y) * progress
                # Note: Arc would be in Z dimension in 3D, here we simulate as slight Y variance
                current_y += arc_height * random.uniform(-0.5, 0.5)
            else:
                current_x = start_x + (end_x - start_x) * progress
                current_y = start_y + (end_y - start_y) * progress
            
            # Bounds checking
            current_x = max(0, min(self.RINK_LENGTH, current_x))
            current_y = max(0, min(self.RINK_WIDTH, current_y))
            
            timestamp = (duration / steps) * i
            
            puck_events.append({
                'timestamp': timestamp,
                'duration': duration / steps,
                'type': 'PUCK_MOVEMENT',
                'details': {
                    'puck_position': (current_x, current_y),
                    'movement_type': movement_type,
                    'speed': speed,
                    'progress': progress
                }
            })
        
        # Update puck position
        self.puck_position = (end_x, end_y)
        
        return puck_events

    def generate_coordinate_event(self, event_type: str, primary_player_id: str, 
                                 secondary_player_id: Optional[str] = None, 
                                 **kwargs) -> Dict:
        """Generate a complete event with realistic coordinates"""
        
        if event_type == "SHOT":
            return self._generate_shot_event(primary_player_id, **kwargs)
        elif event_type == "PASS":
            return self._generate_pass_event(primary_player_id, secondary_player_id, **kwargs)
        elif event_type == "HIT":
            return self._generate_hit_event(primary_player_id, secondary_player_id, **kwargs)
        elif event_type == "FACEOFF":
            return self._generate_faceoff_event(primary_player_id, secondary_player_id, **kwargs)
        else:
            # Generic event
            position = self.player_positions.get(primary_player_id, (100, 42.5))
            return {
                'timestamp': kwargs.get('timestamp', 0),
                'duration': kwargs.get('duration', 1.0),
                'type': event_type,
                'details': {
                    'player_id': primary_player_id,
                    'position': position,
                    'zone': self.get_zone_from_coordinates(*position)
                }
            }

    def _generate_shot_event(self, shooter_id: str, **kwargs) -> Dict:
        """Generate detailed shot event with coordinates and danger analysis"""
        shooter_pos = self.player_positions.get(shooter_id, (100, 42.5))
        attacking_home = kwargs.get('attacking_home_goal', False)
        
        shot_data = self.generate_shot_coordinates(shooter_pos, attacking_home)
        
        return {
            'timestamp': kwargs.get('timestamp', 0),
            'duration': 0.5,
            'type': 'SHOT',
            'details': {
                'shooter_id': shooter_id,
                'puck_start_pos': shot_data['shot_position'],
                'target_pos': shot_data['target_position'], 
                'distance': shot_data['distance'],
                'angle': shot_data['angle'],
                'danger_level': shot_data['danger_level'].value,
                'expected_goal': shot_data['expected_goal'],
                'zone': shot_data['zone'].value,
                'attacking_home_goal': attacking_home
            }
        }

    def _generate_pass_event(self, passer_id: str, receiver_id: str, **kwargs) -> Dict:
        """Generate pass event with coordinate tracking"""
        passer_pos = self.player_positions.get(passer_id, (100, 42.5))
        receiver_pos = self.player_positions.get(receiver_id, (110, 45))
        
        distance = math.sqrt((receiver_pos[0] - passer_pos[0])**2 + (receiver_pos[1] - passer_pos[1])**2)
        
        return {
            'timestamp': kwargs.get('timestamp', 0),
            'duration': max(0.3, distance / 40),  # 40 fps pass speed
            'type': 'PASS',
            'details': {
                'passer_id': passer_id,
                'receiver_id': receiver_id,
                'puck_start_pos': passer_pos,
                'puck_end_pos': receiver_pos,
                'distance': distance,
                'zone_start': self.get_zone_from_coordinates(*passer_pos).value,
                'zone_end': self.get_zone_from_coordinates(*receiver_pos).value
            }
        }

    def _generate_hit_event(self, hitter_id: str, target_id: str, **kwargs) -> Dict:
        """Generate hit event with coordinate collision detection"""
        hitter_pos = self.player_positions.get(hitter_id, (100, 42.5))
        target_pos = self.player_positions.get(target_id, (105, 42.5))
        
        # Calculate hit impact position (between the two players)
        impact_x = (hitter_pos[0] + target_pos[0]) / 2
        impact_y = (hitter_pos[1] + target_pos[1]) / 2
        
        return {
            'timestamp': kwargs.get('timestamp', 0),
            'duration': 0.3,
            'type': 'HIT',
            'details': {
                'hitter_id': hitter_id,
                'target_id': target_id,
                'impact_position': (impact_x, impact_y),
                'hitter_position': hitter_pos,
                'target_position': target_pos,
                'zone': self.get_zone_from_coordinates(impact_x, impact_y).value
            }
        }

    def _generate_faceoff_event(self, home_center_id: str, away_center_id: str, **kwargs) -> Dict:
        """Generate faceoff event at specific coordinate location"""
        # Determine faceoff location
        faceoff_locations = {
            'center_ice': (100, 42.5),
            'home_defensive': (33, 42.5),
            'home_left': (33, 22),
            'home_right': (33, 63),
            'away_defensive': (167, 42.5),
            'away_left': (167, 22),
            'away_right': (167, 63)
        }
        
        location = kwargs.get('faceoff_location', 'center_ice')
        faceoff_pos = faceoff_locations.get(location, (100, 42.5))
        
        # Update player positions for faceoff
        self.player_positions[home_center_id] = faceoff_pos
        self.player_positions[away_center_id] = faceoff_pos
        
        return {
            'timestamp': kwargs.get('timestamp', 0),
            'duration': 1.0,
            'type': 'FACEOFF',
            'details': {
                'home_center_id': home_center_id,
                'away_center_id': away_center_id,
                'faceoff_position': faceoff_pos,
                'location': location,
                'zone': self.get_zone_from_coordinates(*faceoff_pos).value
            }
        }

    def get_coordinate_summary(self) -> Dict:
        """Get summary of coordinate-based analytics"""
        shot_zones = {}
        danger_distribution = {'very_high': 0, 'high': 0, 'medium': 0, 'low': 0}
        
        for shot in self.shot_locations:
            zone = shot.get('zone', 'unknown')
            danger = shot.get('danger_level', 'low')
            
            shot_zones[zone] = shot_zones.get(zone, 0) + 1
            danger_distribution[danger] = danger_distribution.get(danger, 0) + 1
        
        return {
            'total_shots': len(self.shot_locations),
            'shot_zones': shot_zones,
            'danger_distribution': danger_distribution,
            'high_danger_percentage': (danger_distribution['very_high'] + danger_distribution['high']) / max(1, len(self.shot_locations)) * 100,
            'average_shot_distance': sum(shot.get('distance', 30) for shot in self.shot_locations) / max(1, len(self.shot_locations))
        }
