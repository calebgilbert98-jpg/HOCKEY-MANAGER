# player_generator.py
# Comprehensive Player Generation System for Hockey Manager
# Handles both rookie/prospect generation and main player database creation

import random
import math
import itertools
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from game_classes import Player, PlayerPosition, GameBalance
from draft_generator import (
    FIRST_NAMES, LAST_NAMES, BIRTHPLACES, COUNTRY_DISTRIBUTION, 
    get_random_nationality, get_random_name, get_random_birthplace,
    get_random_position, ARCHETYPES, get_archetype_for_position
)

# --- Enhanced Player Generation Constants ---

# League and skill tiers for different player categories
LEAGUE_TIERS = {
    "NHL_ELITE": {"min_overall": 85, "max_overall": 99, "description": "Elite NHL superstars"},
    "NHL_STARTER": {"min_overall": 75, "max_overall": 89, "description": "NHL starters and core players"},
    "NHL_DEPTH": {"min_overall": 65, "max_overall": 79, "description": "NHL depth players and role players"},
    "AHL_VETERAN": {"min_overall": 60, "max_overall": 74, "description": "AHL veterans with NHL experience"},
    "AHL_PROSPECT": {"min_overall": 55, "max_overall": 69, "description": "AHL prospects developing"},
    "JUNIOR_ELITE": {"min_overall": 50, "max_overall": 65, "description": "Elite junior players"},
    "JUNIOR_PROSPECT": {"min_overall": 40, "max_overall": 59, "description": "Junior prospects"},
    "INTERNATIONAL": {"min_overall": 55, "max_overall": 82, "description": "International league players"},
    "COLLEGE": {"min_overall": 45, "max_overall": 68, "description": "College hockey players"}
}

# Age distributions for different player categories
AGE_DISTRIBUTIONS = {
    "ROOKIE": {"min_age": 18, "max_age": 22, "peak_age": 19},
    "YOUNG": {"min_age": 20, "max_age": 25, "peak_age": 22},
    "PRIME": {"min_age": 24, "max_age": 30, "peak_age": 27},
    "VETERAN": {"min_age": 29, "max_age": 35, "peak_age": 32},
    "OLDTIMER": {"min_age": 33, "max_age": 42, "peak_age": 36}
}

# Contract value ranges based on skill tier and age
CONTRACT_VALUES = {
    "ENTRY_LEVEL": {"min": 750000, "max": 925000, "years": [3]},
    "BRIDGE": {"min": 1000000, "max": 4000000, "years": [2, 3]},
    "STANDARD": {"min": 2000000, "max": 8000000, "years": [3, 4, 5, 6]},
    "PREMIUM": {"min": 6000000, "max": 12000000, "years": [5, 6, 7, 8]},
    "SUPERSTAR": {"min": 9000000, "max": 15000000, "years": [6, 7, 8]},
    "VETERAN": {"min": 750000, "max": 3000000, "years": [1, 2]},
    "AHL": {"min": 70000, "max": 150000, "years": [1, 2]}
}

# Teams for different leagues
NHL_TEAMS = [
    "Boston Bruins", "Buffalo Sabres", "Detroit Red Wings", "Florida Panthers",
    "Montreal Canadiens", "Ottawa Senators", "Tampa Bay Lightning", "Toronto Maple Leafs",
    "Carolina Hurricanes", "Columbus Blue Jackets", "New Jersey Devils", "New York Islanders",
    "New York Rangers", "Philadelphia Flyers", "Pittsburgh Penguins", "Washington Capitals",
    "Chicago Blackhawks", "Colorado Avalanche", "Dallas Stars", "Minnesota Wild",
    "Nashville Predators", "St. Louis Blues", "Winnipeg Jets", "Arizona Coyotes",
    "Calgary Flames", "Edmonton Oilers", "Los Angeles Kings", "San Jose Sharks",
    "Seattle Kraken", "Vancouver Canucks", "Anaheim Ducks", "Vegas Golden Knights"
]

AHL_TEAMS = [
    "Providence Bruins", "Rochester Americans", "Grand Rapids Griffins", "Syracuse Crunch",
    "Laval Rocket", "Belleville Senators", "Toronto Marlies", "Charlotte Checkers",
    "Cleveland Monsters", "Utica Devils", "Bridgeport Islanders", "Hartford Wolf Pack",
    "Lehigh Valley Phantoms", "Wilkes-Barre/Scranton Penguins", "Hershey Bears",
    "Rockford IceHogs", "Colorado Eagles", "Texas Stars", "Iowa Wild",
    "Milwaukee Admirals", "Springfield Thunderbirds", "Manitoba Moose", "Tucson Roadrunners",
    "Calgary Wranglers", "Bakersfield Condors", "Ontario Reign", "San Jose Barracuda",
    "Coachella Valley Firebirds", "Abbotsford Canucks", "San Diego Gulls", "Henderson Silver Knights"
]

INTERNATIONAL_LEAGUES = [
    "KHL", "SHL", "Liiga", "NLA", "DEL", "EIHL", "Czech Extraliga", 
    "Slovak Extraliga", "EBEL", "GET-ligaen", "Metal Ligaen", "HockeyAllsvenskan"
]

JUNIOR_LEAGUES = [
    "OHL", "WHL", "QMJHL", "USHL", "BCHL", "AJHL", "SJHL", "MJHL",
    "NOJHL", "OJHL", "CCHL", "MHL", "VHL", "J20 SuperElit", "U20 SM-sarja"
]

COLLEGE_CONFERENCES = [
    "Hockey East", "ECAC", "Big Ten", "NCHC", "WCHA", "Atlantic Hockey", "CHA"
]

# Potential grades with development curves
POTENTIAL_GRADES = {
    "A+": {"development_speed": 1.5, "ceiling_modifier": 1.3, "probability": 0.005},
    "A": {"development_speed": 1.4, "ceiling_modifier": 1.25, "probability": 0.015},
    "A-": {"development_speed": 1.3, "ceiling_modifier": 1.2, "probability": 0.03},
    "B+": {"development_speed": 1.2, "ceiling_modifier": 1.15, "probability": 0.05},
    "B": {"development_speed": 1.1, "ceiling_modifier": 1.1, "probability": 0.10},
    "B-": {"development_speed": 1.0, "ceiling_modifier": 1.05, "probability": 0.15},
    "C+": {"development_speed": 0.9, "ceiling_modifier": 1.0, "probability": 0.15},
    "C": {"development_speed": 0.8, "ceiling_modifier": 0.95, "probability": 0.20},
    "C-": {"development_speed": 0.7, "ceiling_modifier": 0.9, "probability": 0.15},
    "D": {"development_speed": 0.6, "ceiling_modifier": 0.85, "probability": 0.10},
    "F": {"development_speed": 0.5, "ceiling_modifier": 0.8, "probability": 0.05}
}

class PlayerGenerator:
    """Comprehensive player generation system for Hockey Manager."""
    
    def __init__(self):
        self.generated_names = set()  # Track generated names to avoid duplicates
        self.player_id_counter = 10000  # Start IDs at 10000
    
    def get_unique_id(self) -> str:
        """Generate a unique player ID."""
        self.player_id_counter += 1
        return f"player_{self.player_id_counter}"
    
    def get_unique_name(self, nationality: str, max_attempts: int = 50) -> Tuple[str, str]:
        """Generate a unique name that hasn't been used yet."""
        attempts = 0
        while attempts < max_attempts:
            first_name, last_name = get_random_name(nationality)
            full_name = f"{first_name} {last_name}"
            
            if full_name not in self.generated_names:
                self.generated_names.add(full_name)
                return first_name, last_name
            
            attempts += 1
        
        # If we can't find a unique name, add a number
        first_name, last_name = get_random_name(nationality)
        base_name = f"{first_name} {last_name}"
        counter = 1
        while f"{base_name} {counter}" in self.generated_names:
            counter += 1
        
        unique_name = f"{base_name} {counter}"
        self.generated_names.add(unique_name)
        return first_name, f"{last_name} {counter}"
    
    def get_random_potential(self) -> str:
        """Get a random potential grade based on probability distribution."""
        grades = list(POTENTIAL_GRADES.keys())
        probabilities = [POTENTIAL_GRADES[grade]["probability"] for grade in grades]
        return random.choices(grades, weights=probabilities, k=1)[0]
    
    def get_base_attributes(self, skill_tier: str, age: int, position: PlayerPosition) -> Dict[str, int]:
        """Generate base attributes for a player based on skill tier and age."""
        tier_info = LEAGUE_TIERS[skill_tier]
        
        # Age factor affects attribute ranges
        if age <= 22:
            age_factor = 0.9  # Young players have lower current skills
        elif age <= 28:
            age_factor = 1.0  # Prime age
        elif age <= 33:
            age_factor = 0.95  # Slight decline
        else:
            age_factor = 0.85  # Noticeable decline
        
        # Base attribute range (50-point scale derived from tier's overall range)
        base_min = max(5, int(tier_info["min_overall"] * 0.5 * age_factor))
        base_max = min(50, int(tier_info["max_overall"] * 0.5 * age_factor))
        
        # Generate base attributes
        attributes = {}
        
        # Core attributes for all players
        core_attributes = [
            'skating', 'shooting', 'passing', 'checking', 'strength',
            'determination', 'teamwork', 'leadership', 'discipline', 'flair',
            'stickhandling', 'vision', 'shooting_accuracy', 'shooting_power',
            'passing_accuracy', 'passing_creativity', 'puck_protection',
            'deflections', 'shot_blocking', 'hockey_iq', 'composure',
            'aggressiveness', 'work_rate', 'anticipation', 'decision_making',
            'focus', 'confidence', 'acceleration', 'balance', 'endurance',
            'agility', 'speed', 'stamina', 'durability', 'off_the_puck',
            'wristshot', 'slapshot', 'pokecheck', 'bodycheck', 'one_timer',
            'backhand', 'screen_shots', 'loose_puck', 'creativity', 'pressure_player',
            'deking', 'offensive_awareness', 'defensive_awareness'
        ]
        
        # Position-specific attributes
        if position == PlayerPosition.CENTER:
            core_attributes.extend(['faceoffs', 'faceoff_wins'])
        elif position == PlayerPosition.GOALIE:
            core_attributes.extend([
                'goaltending', 'reflexes', 'positioning', 'rebound_control',
                'puck_handling', 'glove_hand', 'stick_side', 'breakaway_skill'
            ])
        
        # Generate attributes with some variation
        for attr in core_attributes:
            # Add some randomness to the range
            variation = random.randint(-2, 3)
            attr_min = max(GameBalance.MIN_ATTRIBUTE, base_min + variation)
            attr_max = min(GameBalance.MAX_ATTRIBUTE, base_max + variation)
            
            if attr_min >= attr_max:
                attr_max = attr_min + 1
            
            attributes[attr] = random.randint(attr_min, attr_max)
        
        return attributes
    
    def apply_archetype_modifiers(self, player: Player, archetype_name: str, archetype_data: Dict) -> None:
        """Apply archetype-specific attribute modifiers to a player."""
        # Apply attribute bonuses from archetype (archetype ranges are 20-scale; convert to 50-scale)
        for attr, (min_bonus, max_bonus) in archetype_data.get("attributes", {}).items():
            if hasattr(player, attr):
                min_b = int(min_bonus * 2.5)
                max_b = int(max_bonus * 2.5)
                current_value = getattr(player, attr)
                bonus = random.randint(min_b - current_value, max_b - current_value)
                bonus = max(-5, min(8, bonus))  # Limit bonus range
                new_value = max(GameBalance.MIN_ATTRIBUTE, 
                              min(GameBalance.MAX_ATTRIBUTE, current_value + bonus))
                setattr(player, attr, new_value)
        
        # Apply tendencies
        for tendency, (min_val, max_val) in archetype_data.get("tendency", {}).items():
            if hasattr(player, tendency):
                setattr(player, tendency, random.randint(min_val, max_val))
    
    def apply_potential_modifiers(self, player: Player, potential_grade: str) -> None:
        """Apply potential-based modifiers to player attributes."""
        potential_info = POTENTIAL_GRADES[potential_grade]
        ceiling_modifier = potential_info["ceiling_modifier"]
        
        # High potential players get small boosts to key attributes
        if ceiling_modifier > 1.0:
            boost_amount = int((ceiling_modifier - 1.0) * 10)
            
            # Boost key attributes based on position
            if player.primary_position == PlayerPosition.GOALIE:
                key_attrs = ['goaltending', 'reflexes', 'positioning']
            else:
                key_attrs = ['skating', 'hockey_iq', 'composure']
            
            for attr in key_attrs:
                if hasattr(player, attr):
                    current_value = getattr(player, attr)
                    new_value = min(GameBalance.MAX_ATTRIBUTE, current_value + boost_amount)
                    setattr(player, attr, new_value)
    
    def determine_contract_info(self, player: Player, skill_tier: str) -> Tuple[int, int]:
        """Determine appropriate contract salary and length for a player."""
        overall = player.overall_rating()
        age = player.age
        
        # Determine contract category
        if age <= 22 and overall < 44:
            contract_type = "ENTRY_LEVEL"
        elif age <= 25 and overall < 47:
            contract_type = "BRIDGE"
        elif overall >= 52:
            contract_type = "SUPERSTAR"
        elif overall >= 49:
            contract_type = "PREMIUM"
        elif age >= 33:
            contract_type = "VETERAN"
        elif "AHL" in skill_tier:
            contract_type = "AHL"
        else:
            contract_type = "STANDARD"
        
        contract_info = CONTRACT_VALUES[contract_type]
        
        # Calculate salary based on overall rating
        salary_range = contract_info["max"] - contract_info["min"]
        salary_factor = (overall - 30) / 25  # Normalize to 0-1 range
        salary_factor = max(0, min(1, salary_factor))
        
        base_salary = contract_info["min"] + (salary_range * salary_factor)
        
        # Add some randomness
        variation = random.uniform(0.85, 1.15)
        final_salary = int(base_salary * variation)
        
        # Ensure within bounds
        final_salary = max(contract_info["min"], min(contract_info["max"], final_salary))
        
        # Round to nearest 25k
        final_salary = round(final_salary / 25000) * 25000
        
        # Contract length
        contract_length = random.choice(contract_info["years"])
        
        return final_salary, contract_length
    
    def create_player(self, 
                     skill_tier: str = "NHL_DEPTH",
                     age_category: str = "PRIME",
                     position: Optional[PlayerPosition] = None,
                     nationality: Optional[str] = None,
                     team_name: str = "Free Agent") -> Player:
        """Create a single player with specified parameters."""
        
        # Determine nationality
        if nationality is None:
            nationality = get_random_nationality()
        
        # Generate unique name
        first_name, last_name = self.get_unique_name(nationality)
        birthplace = get_random_birthplace(nationality)
        
        # Determine position
        if position is None:
            position = get_random_position()
        
        # Determine age
        age_info = AGE_DISTRIBUTIONS[age_category]
        # Weight towards peak age
        age_weights = []
        for age in range(age_info["min_age"], age_info["max_age"] + 1):
            distance_from_peak = abs(age - age_info["peak_age"])
            weight = max(1, 5 - distance_from_peak)
            age_weights.append(weight)
        
        age = random.choices(
            range(age_info["min_age"], age_info["max_age"] + 1),
            weights=age_weights,
            k=1
        )[0]
        
        # Create player with basic info
        player = Player(
            first_name=first_name,
            last_name=last_name,
            age=age,
            primary_position=position,
            team_name=team_name
        )
        
        # Set additional properties
        player.birthplace = birthplace
        player.nationality = nationality
        
        # Get potential grade
        potential_grade = self.get_random_potential()
        player.potential_grade = potential_grade
        
        # Generate base attributes
        base_attributes = self.get_base_attributes(skill_tier, age, position)
        
        # Apply attributes to player
        for attr, value in base_attributes.items():
            setattr(player, attr, value)
        
        # Get and apply archetype
        archetype_name, archetype_data = get_archetype_for_position(position)
        self.apply_archetype_modifiers(player, archetype_name, archetype_data)

        # Apply potential modifiers
        self.apply_potential_modifiers(player, potential_grade)

        # Classify the true archetype from final attributes: a player IS what
        # his attributes say, so scouting/chemistry/sim all see the real thing
        try:
            from player_archetypes import classify_player
            player.archetype = classify_player(player)
        except Exception:
            player.archetype = archetype_name
        
        # Set contract info if not free agent
        if team_name != "Free Agent":
            salary, contract_length = self.determine_contract_info(player, skill_tier)
            player.contract.salary = salary
            player.contract.years_remaining = contract_length
        
        # Set some additional properties
        player.shooting_tendency = random.randint(30, 70)
        player.hitting_tendency = random.randint(30, 70)
        player.nhl_games_played = random.randint(0, min(age * 40, 1000)) if age > 18 else 0
        
        return player
    
    def generate_rookie_class(self, size: int = 224) -> List[Player]:
        """Generate a class of rookie prospects (18-22 year olds)."""
        rookies = []
        
        print(f"Generating rookie class of {size} players...")
        
        # Ensure minimum representation per position
        positions = list(PlayerPosition)
        min_per_position = max(1, size // len(positions))
        position_counts = {pos: 0 for pos in positions}
        
        for i in range(size):
            # Force position if we need more of a specific position
            forced_position = None
            for pos, count in position_counts.items():
                if count < min_per_position:
                    forced_position = pos
                    break
            
            # Determine skill tier for rookie (mostly prospects with some variation)
            skill_tier_weights = {
                "JUNIOR_ELITE": 0.15,
                "JUNIOR_PROSPECT": 0.60,
                "COLLEGE": 0.20,
                "AHL_PROSPECT": 0.05
            }
            
            skill_tier = random.choices(
                list(skill_tier_weights.keys()),
                weights=list(skill_tier_weights.values()),
                k=1
            )[0]
            
            # Create rookie
            rookie = self.create_player(
                skill_tier=skill_tier,
                age_category="ROOKIE",
                position=forced_position
            )
            
            # Set appropriate team for rookies
            if skill_tier == "JUNIOR_ELITE" or skill_tier == "JUNIOR_PROSPECT":
                rookie.team_name = random.choice(JUNIOR_LEAGUES) + " Team"
            elif skill_tier == "COLLEGE":
                rookie.team_name = random.choice(COLLEGE_CONFERENCES) + " Team"
            else:
                rookie.team_name = random.choice(AHL_TEAMS)
            
            rookies.append(rookie)
            position_counts[rookie.primary_position] += 1
        
        # Sort by overall rating for draft order simulation
        rookies.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        print(f"Generated {len(rookies)} rookies")
        
        return rookies
    
    def generate_nhl_players(self, size: int = 800) -> List[Player]:
        """Generate NHL-level players for the main database."""
        nhl_players = []
        
        print(f"Generating {size} NHL players...")
        
        # Define skill tier distribution for NHL
        skill_tier_distribution = {
            "NHL_ELITE": 0.05,      # 5% elite players
            "NHL_STARTER": 0.35,    # 35% starter-level
            "NHL_DEPTH": 0.45,      # 45% depth players
            "AHL_VETERAN": 0.15     # 15% AHL veterans with NHL experience
        }
        
        # Age distribution for NHL
        age_category_distribution = {
            "YOUNG": 0.20,
            "PRIME": 0.50,
            "VETERAN": 0.25,
            "OLDTIMER": 0.05
        }
        
        # Track position and team distribution
        teams_cycle = itertools.cycle(NHL_TEAMS)
        position_counts = {pos: 0 for pos in PlayerPosition}
        
        for i in range(size):
            # Determine skill tier
            skill_tier = random.choices(
                list(skill_tier_distribution.keys()),
                weights=list(skill_tier_distribution.values()),
                k=1
            )[0]
            
            # Determine age category
            age_category = random.choices(
                list(age_category_distribution.keys()),
                weights=list(age_category_distribution.values()),
                k=1
            )[0]
            
            # Create player as free agent initially (will be assigned to teams later)
            player = self.create_player(
                skill_tier=skill_tier,
                age_category=age_category,
                team_name="Free Agent"
            )
            
            nhl_players.append(player)
            position_counts[player.primary_position] += 1
        
        print(f"Generated {len(nhl_players)} NHL players")
        
        return nhl_players
    
    def generate_international_players(self, size: int = 300) -> List[Player]:
        """Generate international league players."""
        international_players = []
        
        print(f"Generating {size} international players...")
        
        # International leagues focus on certain nationalities
        international_nationalities = {
            "Russia": 0.25,
            "Sweden": 0.20,
            "Finland": 0.15,
            "Czech": 0.10,
            "Other": 0.30
        }
        
        for i in range(size):
            # Choose nationality
            nationality = random.choices(
                list(international_nationalities.keys()),
                weights=list(international_nationalities.values()),
                k=1
            )[0]
            
            # Choose league
            league = random.choice(INTERNATIONAL_LEAGUES)
            team_name = f"{league} Team"
            
            # Create player
            player = self.create_player(
                skill_tier="INTERNATIONAL",
                age_category=random.choice(["YOUNG", "PRIME", "VETERAN"]),
                nationality=nationality,
                team_name=team_name
            )
            
            international_players.append(player)
        
        print(f"Generated {len(international_players)} international players")
        
        return international_players
    
    def generate_complete_database(self) -> Dict[str, List[Player]]:
        """Generate a complete player database with all categories."""
        print("Generating complete player database...")
        
        database = {
            "nhl_players": self.generate_nhl_players(800),
            "rookies": self.generate_rookie_class(224),
            "international": self.generate_international_players(300),
            "free_agents": []
        }
        
        # Generate some free agents from each category
        print("Generating free agents...")
        
        # NHL free agents
        for _ in range(50):
            player = self.create_player(
                skill_tier=random.choice(["NHL_DEPTH", "AHL_VETERAN"]),
                age_category=random.choice(["PRIME", "VETERAN", "OLDTIMER"]),
                team_name="Free Agent"
            )
            database["free_agents"].append(player)
        
        # International free agents
        for _ in range(30):
            player = self.create_player(
                skill_tier="INTERNATIONAL",
                age_category=random.choice(["YOUNG", "PRIME", "VETERAN"]),
                nationality=random.choice(["Russia", "Sweden", "Finland", "Czech", "Other"]),
                team_name="Free Agent"
            )
            database["free_agents"].append(player)
        
        total_players = sum(len(players) for players in database.values())
        print(f"Complete database generated with {total_players} total players")
        
        return database

# Convenience functions for easy access
def generate_rookies(size: int = 224) -> List[Player]:
    """Generate a rookie class."""
    generator = PlayerGenerator()
    return generator.generate_rookie_class(size)

def generate_nhl_database(size: int = 800) -> List[Player]:
    """Generate NHL players database."""
    generator = PlayerGenerator()
    return generator.generate_nhl_players(size)

def generate_single_player(skill_level: str = "NHL_DEPTH", 
                          age_category: str = "PRIME",
                          position: Optional[PlayerPosition] = None) -> Player:
    """Generate a single player with specified parameters."""
    generator = PlayerGenerator()
    return generator.create_player(skill_level, age_category, position)

def generate_complete_database() -> Dict[str, List[Player]]:
    """Generate a complete player database."""
    generator = PlayerGenerator()
    return generator.generate_complete_database()

# Example usage and testing
if __name__ == "__main__":
    # Test generation
    generator = PlayerGenerator()
    
    # Test single player generation
    print("Testing single player generation...")
    test_player = generator.create_player("NHL_ELITE", "PRIME", PlayerPosition.CENTER)
    print(f"Generated: {test_player.full_name}, {test_player.age} years old, {test_player.primary_position.name}")
    print(f"Overall: {test_player.overall_rating()}, Potential: {test_player.potential_grade}")
    print(f"Team: {test_player.team_name}, Salary: ${test_player.contract.salary:,}")
    
    # Test rookie class generation
    print("\nTesting rookie class generation...")
    rookies = generator.generate_rookie_class(50)
    print(f"Top 5 rookies:")
    for i, rookie in enumerate(rookies[:5]):
        print(f"{i+1}. {rookie.full_name} ({rookie.primary_position.name}) - {rookie.overall_rating()} OVR")
