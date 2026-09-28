"""
Advanced Player Development System
Handles age-based progression, training, potential tracking, and skill development
"""

import random
import math
from datetime import date, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
from game_classes import Player, PlayerPosition


class DevelopmentStage(Enum):
    """Different stages of a player's career development"""
    JUNIOR = "junior"           # 16-19: Rapid development
    RISING = "rising"           # 20-23: Strong development  
    PRIME_EARLY = "prime_early" # 24-27: Peak performance, slow improvement
    PRIME = "prime"             # 28-31: Peak performance, maintenance
    VETERAN = "veteran"         # 32-35: Gradual decline
    AGING = "aging"             # 36+: Accelerated decline


class TrainingFocus(Enum):
    """Different training focuses available"""
    SKATING = "skating"
    SHOOTING = "shooting"
    PASSING = "passing"
    DEFENSE = "defense"
    PHYSICAL = "physical"
    MENTAL = "mental"
    GOALTENDING = "goaltending"
    CONDITIONING = "conditioning"


@dataclass
class PlayerPotential:
    """Tracks a player's potential in various attributes"""
    # Core potentials (1-20 scale)
    skating_potential: int = field(default_factory=lambda: random.randint(12, 20))
    shooting_potential: int = field(default_factory=lambda: random.randint(12, 20))
    passing_potential: int = field(default_factory=lambda: random.randint(12, 20))
    checking_potential: int = field(default_factory=lambda: random.randint(12, 20))
    defense_potential: int = field(default_factory=lambda: random.randint(12, 20))
    
    # Mental potentials
    hockey_iq_potential: int = field(default_factory=lambda: random.randint(12, 20))
    determination_potential: int = field(default_factory=lambda: random.randint(12, 20))
    leadership_potential: int = field(default_factory=lambda: random.randint(12, 20))
    
    # Physical potentials
    strength_potential: int = field(default_factory=lambda: random.randint(12, 20))
    conditioning_potential: int = field(default_factory=lambda: random.randint(12, 20))
    
    # Position-specific potentials
    goaltending_potential: int = field(default_factory=lambda: random.randint(12, 20))
    faceoffs_potential: int = field(default_factory=lambda: random.randint(12, 20))
    
    # Development modifiers
    work_ethic: int = field(default_factory=lambda: random.randint(8, 20))  # Affects development speed
    injury_proneness: int = field(default_factory=lambda: random.randint(5, 15))  # Lower = more prone
    
    def get_potential_for_attribute(self, attribute_name: str) -> int:
        """Get the potential for a specific attribute"""
        potential_map = {
            'skating': self.skating_potential,
            'shooting': self.shooting_potential,
            'passing': self.passing_potential,
            'checking': self.checking_potential,
            'defense': self.defense_potential,
            'hockey_iq': self.hockey_iq_potential,
            'determination': self.determination_potential,
            'leadership': self.leadership_potential,
            'strength': self.strength_potential,
            'conditioning': self.conditioning_potential,
            'goaltending': self.goaltending_potential,
            'faceoffs': self.faceoffs_potential,
        }
        return potential_map.get(attribute_name, 15)


@dataclass 
class TrainingProgram:
    """Represents a training program for a player"""
    focus: TrainingFocus
    intensity: int  # 1-10 scale
    duration_weeks: int
    trainer_quality: int  # 1-20 scale (affects effectiveness)
    started_date: date
    player_id: str
    
    @property
    def is_complete(self) -> bool:
        """Check if training program is complete"""
        weeks_elapsed = (date.today() - self.started_date).days // 7
        return weeks_elapsed >= self.duration_weeks
    
    @property
    def progress_percentage(self) -> float:
        """Get completion percentage of training"""
        weeks_elapsed = (date.today() - self.started_date).days // 7
        return min(100.0, (weeks_elapsed / self.duration_weeks) * 100)


@dataclass
class DevelopmentHistory:
    """Tracks a player's development history"""
    attribute_changes: Dict[str, List[Tuple[date, int, str]]] = field(default_factory=dict)  # attr -> [(date, change, reason)]
    training_completed: List[TrainingProgram] = field(default_factory=list)
    development_events: List[Tuple[date, str]] = field(default_factory=list)  # Major development milestones
    
    def add_attribute_change(self, attribute: str, change: int, reason: str):
        """Record an attribute change"""
        if attribute not in self.attribute_changes:
            self.attribute_changes[attribute] = []
        self.attribute_changes[attribute].append((date.today(), change, reason))
    
    def add_development_event(self, event: str):
        """Record a development milestone"""
        self.development_events.append((date.today(), event))


class PlayerDevelopmentEngine:
    """Core engine for player development calculations"""
    
    def __init__(self):
        self.active_training_programs: Dict[str, TrainingProgram] = {}
        self.development_history: Dict[str, DevelopmentHistory] = {}
    
    def get_development_stage(self, player: Player) -> DevelopmentStage:
        """Determine a player's current development stage.

        Development arc shifts the age thresholds:
        - late_bloomer: +2 years (peaks at 28-30 instead of 26-27)
        - early_peak: -2 years (peaks at 24-25 instead of 26-27)
        - standard: no shift
        """
        age = player.age
        arc = getattr(player, 'development_arc', 'standard')

        # Arc shifts thresholds
        shift = 0
        if arc == "late_bloomer":
            shift = 2
        elif arc == "early_peak":
            shift = -2

        if age <= 19 + shift:
            return DevelopmentStage.JUNIOR
        elif age <= 23 + shift:
            return DevelopmentStage.RISING
        elif age <= 27 + shift:
            return DevelopmentStage.PRIME_EARLY
        elif age <= 31 + shift:
            return DevelopmentStage.PRIME
        elif age <= 35 + shift:
            return DevelopmentStage.VETERAN
        else:
            return DevelopmentStage.AGING
    
    def calculate_base_development_rate(self, player: Player) -> float:
        """Calculate base development rate based on age and stage.

        Development arc modifies the rate:
        - late_bloomer: 0.7x in JUNIOR/RISING, 1.3x in PRIME_EARLY/PRIME
        - early_peak: 1.3x in JUNIOR/RISING, 0.7x in PRIME/VETERAN
        - standard: 1.0x (unchanged)
        """
        stage = self.get_development_stage(player)
        
        # Base rates by development stage
        stage_rates = {
            DevelopmentStage.JUNIOR: 0.8,      # High development
            DevelopmentStage.RISING: 0.6,      # Good development
            DevelopmentStage.PRIME_EARLY: 0.3, # Slow improvement
            DevelopmentStage.PRIME: 0.1,       # Maintenance
            DevelopmentStage.VETERAN: -0.2,    # Slight decline
            DevelopmentStage.AGING: -0.5       # Noticeable decline
        }
        
        base_rate = stage_rates[stage]

        # Apply development arc multiplier (additive to engine, not override)
        arc = getattr(player, 'development_arc', 'standard')
        if arc == "late_bloomer":
            if stage in (DevelopmentStage.JUNIOR, DevelopmentStage.RISING):
                base_rate *= 0.7  # Slower early
            elif stage in (DevelopmentStage.PRIME_EARLY, DevelopmentStage.PRIME):
                base_rate *= 1.3  # Stronger/longer peak
            elif stage == DevelopmentStage.VETERAN:
                base_rate *= 0.7  # Slower decline (less negative)
        elif arc == "early_peak":
            if stage in (DevelopmentStage.JUNIOR, DevelopmentStage.RISING):
                base_rate *= 1.3  # Faster early
            elif stage == DevelopmentStage.PRIME_EARLY:
                base_rate *= 0.5  # Peak ends sooner
            elif stage == DevelopmentStage.PRIME:
                base_rate -= 0.2  # Early decline (0.1 maintenance -> -0.1)
            elif stage in (DevelopmentStage.VETERAN, DevelopmentStage.AGING):
                base_rate *= 1.3  # Faster decline (more negative)
        
        # Apply potential modifiers based on player's work ethic and
        # determination. Both live on the ~100-scale in the live game, so
        # normalize to the 1-20 scale this formula was written for.
        if hasattr(player, 'work_ethic') and hasattr(player, 'determination'):
            work_ethic_modifier = ((player.work_ethic / 5.0) - 10) * 0.02
            determination_modifier = ((player.determination / 5.0) - 10) * 0.03
            base_rate += work_ethic_modifier + determination_modifier
        
        return base_rate
    
    def calculate_attribute_development(self, player: Player, attribute: str,
                                            coach=None) -> int:
        """Calculate how much an attribute should change"""
        if not hasattr(player, 'potential'):
            return 0
        
        current_value = getattr(player, attribute, 10)
        # Ceiling: the player's touted potential grade, on the live
        # attribute scale (attributes are 1-100 in the live game).
        try:
            _cap = int(player._potential_cap())
        except Exception:
            try:
                _cap = int(getattr(player, 'potential', 13) or 13) * 5
            except Exception:
                _cap = 75
        potential_value = min(_cap + random.randint(-5, 5), 99)
        
        # Don't develop if at or above potential
        if current_value >= potential_value:
            # Small chance of decline if over potential
            if current_value > potential_value and random.random() < 0.1:
                return -1
            return 0
        
        base_rate = self.calculate_base_development_rate(player)
        
        # Distance from potential affects development speed
        potential_gap = potential_value - current_value
        gap_modifier = min(1.0, potential_gap / 25.0)  # Closer to potential = slower development
        
        # Random variance
        variance = random.uniform(0.5, 1.5)
        
        # Calculate development points
        development_points = base_rate * gap_modifier * variance
        # The coach: influence, youth touch, personality, talent.
        if coach is not None:
            try:
                import reputation_system as _rs
                development_points *= _rs.coach_development_factor(player, coach)
            except Exception:
                pass
        
        # Monthly roll of the annual expectation: development_points keeps
        # the original formula (stage rates, work ethic/determination, gap
        # slowdown, variance, coach factor) as expected ANNUAL movement per
        # attribute; each month rolls 1/12th of it, so this pass is texture
        # under the yearly age_one_year main curve.
        if abs(development_points) > 0.05 \
                and random.random() < abs(development_points) / 12.0:
            return 1 if development_points > 0 else -1
        return 0
    
    def apply_training_effects(self, player: Player, training: TrainingProgram) -> Dict[str, int]:
        """Apply training program effects to player attributes"""
        if training.player_id != player.id or not training.is_complete:
            return {}
        
        # Define which attributes each training focus affects
        training_effects = {
            TrainingFocus.SKATING: ['skating', 'conditioning'],
            TrainingFocus.SHOOTING: ['shooting', 'shooting_accuracy'],
            TrainingFocus.PASSING: ['passing', 'vision'],
            TrainingFocus.DEFENSE: ['defense', 'checking'],
            TrainingFocus.PHYSICAL: ['strength', 'checking', 'conditioning'],
            TrainingFocus.MENTAL: ['hockey_iq', 'determination', 'composure'],
            TrainingFocus.GOALTENDING: ['goaltending', 'reflexes', 'positioning'],
            TrainingFocus.CONDITIONING: ['conditioning', 'strength']
        }
        
        affected_attributes = training_effects.get(training.focus, [])
        attribute_changes = {}
        
        for attribute in affected_attributes:
            if hasattr(player, attribute):
                # Training effectiveness based on intensity, trainer quality, and duration
                effectiveness = (
                    training.intensity * 0.3 +
                    training.trainer_quality * 0.4 +
                    min(training.duration_weeks, 12) * 0.3
                ) / 10.0
                
                # Apply randomness and potential limits
                if random.random() < effectiveness:
                    current_value = getattr(player, attribute, 10)
                    potential_value = player.potential.get_potential_for_attribute(attribute) if hasattr(player, 'potential') else 20
                    
                    if current_value < potential_value:
                        change = random.randint(1, 2)
                        new_value = min(potential_value, current_value + change)
                        setattr(player, attribute, new_value)
                        attribute_changes[attribute] = change
                        
                        # Record the change
                        self.record_development_change(player, attribute, change, f"Training: {training.focus.value}")
        
        return attribute_changes
    
    def process_monthly_development(self, player: Player, coach=None) -> Dict[str, int]:
        """Process natural monthly development for a player"""
        if not hasattr(player, 'potential'):
            # Initialize potential if missing
            player.potential = PlayerPotential()
        
        attribute_changes = {}
        
        # List of attributes that can develop
        developable_attributes = [
            'skating', 'shooting', 'passing', 'checking', 'defense',
            'hockey_iq', 'determination', 'leadership', 'strength', 
            'conditioning', 'faceoffs'
        ]
        
        # Add goaltending for goalies
        if player.primary_position == PlayerPosition.GOALIE:
            developable_attributes.extend(['goaltending', 'reflexes', 'positioning'])
        
        # Process each attribute
        for attribute in developable_attributes:
            if hasattr(player, attribute):
                change = self.calculate_attribute_development(player, attribute, coach=coach)
                if change != 0:
                    current_value = getattr(player, attribute)
                    new_value = max(1, min(100, current_value + change))
                    setattr(player, attribute, new_value)
                    attribute_changes[attribute] = change
                    
                    # Record the change
                    reason = "Natural development" if change > 0 else "Age-related decline"
                    self.record_development_change(player, attribute, change, reason)
        
        return attribute_changes
    
    def record_development_change(self, player: Player, attribute: str, change: int, reason: str):
        """Record a development change in the player's history"""
        if player.id not in self.development_history:
            self.development_history[player.id] = DevelopmentHistory()
        
        self.development_history[player.id].add_attribute_change(attribute, change, reason)
    
    def start_training_program(self, player: Player, focus: TrainingFocus, 
                             intensity: int, duration_weeks: int, trainer_quality: int) -> bool:
        """Start a new training program for a player"""
        if player.id in self.active_training_programs:
            return False  # Player already in training
        
        program = TrainingProgram(
            focus=focus,
            intensity=intensity,
            duration_weeks=duration_weeks,
            trainer_quality=trainer_quality,
            started_date=date.today(),
            player_id=player.id
        )
        
        self.active_training_programs[player.id] = program
        return True
    
    def complete_training_programs(self) -> Dict[str, TrainingProgram]:
        """Check for and complete any finished training programs"""
        completed = {}
        
        for player_id, program in list(self.active_training_programs.items()):
            if program.is_complete:
                completed[player_id] = program
                del self.active_training_programs[player_id]
        
        return completed
    
    def get_player_development_summary(self, player: Player) -> Dict:
        """Get a comprehensive development summary for a player"""
        stage = self.get_development_stage(player)
        base_rate = self.calculate_base_development_rate(player)
        
        # Calculate overall potential vs current
        if hasattr(player, 'potential'):
            potential_rating = self.calculate_potential_overall(player)
            current_rating = player.overall_rating()
            potential_gap = potential_rating - current_rating
        else:
            potential_rating = 0
            current_rating = player.overall_rating()
            potential_gap = 0
        
        summary = {
            'development_stage': stage.value,
            'base_development_rate': base_rate,
            'current_overall': current_rating,
            'potential_overall': potential_rating,
            'potential_gap': potential_gap,
            'active_training': self.active_training_programs.get(player.id),
            'development_outlook': self.get_development_outlook(player)
        }
        
        return summary
    
    def calculate_potential_overall(self, player: Player) -> int:
        """Calculate what the player's overall rating could be at full potential"""
        if not hasattr(player, 'potential'):
            return player.overall_rating()
        
        # Temporarily set attributes to potential values and calculate rating
        original_values = {}
        
        # Store original values
        for attr in ['skating', 'shooting', 'passing', 'checking', 'defense', 
                    'hockey_iq', 'determination', 'leadership', 'strength', 'conditioning']:
            if hasattr(player, attr):
                original_values[attr] = getattr(player, attr)
                # Set to potential (use player's potential as base with some variation)
                potential_val = min(player.potential + random.randint(-1, 1), 20)
                setattr(player, attr, potential_val)
        
        # Calculate potential rating
        potential_rating = player.overall_rating()
        
        # Restore original values
        for attr, value in original_values.items():
            setattr(player, attr, value)
        
        return potential_rating
    
    def get_development_outlook(self, player: Player) -> str:
        """Get a text description of the player's development outlook"""
        stage = self.get_development_stage(player)
        base_rate = self.calculate_base_development_rate(player)
        
        if base_rate > 0.5:
            return "Excellent development potential"
        elif base_rate > 0.2:
            return "Good development potential" 
        elif base_rate > -0.1:
            return "Maintaining current level"
        elif base_rate > -0.3:
            return "Beginning to decline"
        else:
            return "Significant decline expected"


def initialize_player_potential(player: Player) -> PlayerPotential:
    """Initialize potential for an existing player based on their current attributes"""
    potential = PlayerPotential()
    
    # Set potentials based on current values plus some growth room
    attributes = ['skating', 'shooting', 'passing', 'checking', 'defense', 
                 'hockey_iq', 'determination', 'leadership', 'strength', 'conditioning']
    
    for attr in attributes:
        if hasattr(player, attr):
            current_value = getattr(player, attr)
            # Potential is current value + 0-5 points, capped at 20
            growth_room = random.randint(0, 5)
            potential_value = min(20, current_value + growth_room)
            
            # Set the corresponding potential
            potential_attr = f"{attr}_potential"
            if hasattr(potential, potential_attr):
                setattr(potential, potential_attr, potential_value)
    
    return potential


def test_development_system():
    """Test the development system with sample players"""
    from game_classes import Player, PlayerPosition
    
    print("=== TESTING PLAYER DEVELOPMENT SYSTEM ===")
    
    # Create development engine
    dev_engine = PlayerDevelopmentEngine()
    
    # Create test players
    young_player = Player("Connor", "McDavid", 20, PlayerPosition.CENTER)
    young_player.id = "young_test"
    young_player.potential = PlayerPotential()
    
    veteran_player = Player("Sidney", "Crosby", 35, PlayerPosition.CENTER)
    veteran_player.id = "veteran_test"  
    veteran_player.potential = PlayerPotential()
    
    # Test development summaries
    print("\n--- Development Summaries ---")
    young_summary = dev_engine.get_player_development_summary(young_player)
    print(f"Young Player ({young_player.full_name}):")
    print(f"  Stage: {young_summary['development_stage']}")
    print(f"  Base Rate: {young_summary['base_development_rate']:.2f}")
    print(f"  Current Overall: {young_summary['current_overall']}")
    print(f"  Potential Overall: {young_summary['potential_overall']}")
    print(f"  Outlook: {young_summary['development_outlook']}")
    
    print(f"\nVeteran Player ({veteran_player.full_name}):")
    veteran_summary = dev_engine.get_player_development_summary(veteran_player)
    print(f"  Stage: {veteran_summary['development_stage']}")
    print(f"  Base Rate: {veteran_summary['base_development_rate']:.2f}")
    print(f"  Current Overall: {veteran_summary['current_overall']}")
    print(f"  Potential Overall: {veteran_summary['potential_overall']}")
    print(f"  Outlook: {veteran_summary['development_outlook']}")
    
    # Test training system
    print(f"\n--- Training System ---")
    success = dev_engine.start_training_program(
        young_player, TrainingFocus.SKATING, intensity=8, duration_weeks=6, trainer_quality=15
    )
    print(f"Started training program: {success}")
    
    if young_player.id in dev_engine.active_training_programs:
        program = dev_engine.active_training_programs[young_player.id]
        print(f"Training Focus: {program.focus.value}")
        print(f"Progress: {program.progress_percentage:.1f}%")
    
    # Test monthly development
    print(f"\n--- Monthly Development ---")
    young_changes = dev_engine.process_monthly_development(young_player)
    veteran_changes = dev_engine.process_monthly_development(veteran_player)
    
    print(f"Young player changes: {young_changes}")
    print(f"Veteran player changes: {veteran_changes}")
    
    print("\nDevelopment system test completed!")


if __name__ == "__main__":
    test_development_system()
