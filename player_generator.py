# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# player_generator.py
# Comprehensive Player Generation System for Hockey Manager
# Handles both rookie/prospect generation and main player database creation

import random
import itertools
from typing import List, Dict, Tuple, Optional
from game_classes import Player, PlayerPosition, GameBalance, position_label
from draft_generator import (get_random_nationality, get_random_name, get_random_birthplace, get_random_position, get_archetype_for_position)

# --- Enhanced Player Generation Constants ---

# League and skill tiers for different player categories
LEAGUE_TIERS = {
    "NHL_ELITE": {"min_overall": 80, "max_overall": 92, "description": "Elite NHL superstars"},
    "NHL_STARTER": {"min_overall": 70, "max_overall": 82, "description": "NHL starters and core players"},
    "NHL_DEPTH": {"min_overall": 60, "max_overall": 72, "description": "NHL depth players and role players"},
    "AHL_VETERAN": {"min_overall": 55, "max_overall": 67, "description": "AHL veterans with NHL experience"},
    "AHL_PROSPECT": {"min_overall": 52, "max_overall": 66, "description": "AHL prospects developing"},
    "JUNIOR_ELITE": {"min_overall": 48, "max_overall": 62, "description": "Elite junior players"},
    "JUNIOR_PROSPECT": {"min_overall": 38, "max_overall": 56, "description": "Junior prospects"},
    "INTERNATIONAL": {"min_overall": 52, "max_overall": 78, "description": "International league players"},
    "COLLEGE": {"min_overall": 42, "max_overall": 64, "description": "College hockey players"}
}

# Age distributions for different player categories
AGE_DISTRIBUTIONS = {
    "ROOKIE": {"min_age": 18, "max_age": 22, "peak_age": 19},
    "YOUNG": {"min_age": 20, "max_age": 25, "peak_age": 22},
    "PRIME": {"min_age": 24, "max_age": 30, "peak_age": 27},
    "VETERAN": {"min_age": 29, "max_age": 35, "peak_age": 32},
    "OLDTIMER": {"min_age": 33, "max_age": 42, "peak_age": 36}
}

# Contract value ranges based on skill tier and age.
# Caleb's original tier structure, rescaled to the 2026-27 economy after
# the biggest spending summer in NHL history. Cap trend: $88M (2024-25) ->
# $95.5M (2025-26) -> $104M (2026-27) -> $113.5M (2027-28), ~9%/yr, and the
# 2026 summer reset the top of the market: Celebrini 5x$94M ($18.8M AAV,
# richest ever), Kaprizov 8x$136M ($17M), Draisaitl $14M, Eichel 8x$108M
# ($13.5M), Matthews $13.25M, K. Connor 8x$96M ($12M). Agents negotiate in
# cap percentage now: 15% of the $104M cap is $15.6M, so the superstar
# gate runs $14M-$19M with record deals pushing past it.
# NOTE: ENTRY_LEVEL is overridden dynamically inside determine_contract_info
# (new-CBA floor = signing-season league minimum, ceiling = the 9.3(a) max
# annual compensation for the signing season, term 3/2/1 by signing age).
# The static row below is a legacy fallback.
CONTRACT_VALUES = {
    "ENTRY_LEVEL": {"min": 850000, "max": 1025000, "years": [3]},
    "BRIDGE": {"min": 1200000, "max": 5000000, "years": [2, 3]},
    "STANDARD": {"min": 1000000, "max": 6500000, "years": [3, 4, 5, 6]},
    "PREMIUM": {"min": 9000000, "max": 13500000, "years": [5, 6, 7, 8]},
    "SUPERSTAR": {"min": 14000000, "max": 19000000, "years": [6, 7, 8]},
    "VETERAN": {"min": 775000, "max": 3750000, "years": [1, 2]},
    "AHL": {"min": 85000, "max": 200000, "years": [1, 2]}
}

# Above-market inflation: the share of premium/superstar deals that get
# pushed past the gate by a bidding war, and how far past it they go.
# Summer 2026 proved the ceiling is aspirational: Kaprizov's $17M (16.35%
# of the cap) and Celebrini's $18.8M reset what a franchise player costs.
ABOVE_MARKET_SHARE = 0.22
ABOVE_MARKET_BUMP = (1.05, 1.12)
# Superstars get a wider war range: the record deals (Makar $20.4M,
# Celebrini $18.8M, Carlsson $18M, Kaprizov $17M) all came from bidding
# wars pushing 10-25% past the top of the gate.
ABOVE_MARKET_BUMP_STAR = (1.08, 1.28)
# Just under the CBA max (20% of the $104M cap = $20.8M).
ABOVE_MARKET_CEILING = 20500000

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
        
        # Base attribute range (100-point scale, straight from tier's overall range)
        base_min = max(10, int(tier_info["min_overall"] * age_factor))
        base_max = min(99, int(tier_info["max_overall"] * age_factor))
        
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
        
        # Generate attributes with some variation (wider for 100-scale spread)
        for attr in core_attributes:
            # Add some randomness to the range
            variation = random.randint(-6, 8)
            attr_min = max(GameBalance.MIN_ATTRIBUTE, base_min + variation)
            attr_max = min(GameBalance.MAX_ATTRIBUTE, base_max + variation)
            
            if attr_min >= attr_max:
                attr_max = attr_min + 1
            
            attributes[attr] = random.randint(attr_min, attr_max)
        
        return attributes
    
    def apply_archetype_modifiers(self, player: Player, archetype_name: str, archetype_data: Dict) -> None:
        """Apply archetype-specific attribute modifiers to a player."""
        # Archetype gives a modest boost to signature attributes (+2 to +7),
        # not a pull to a fixed range. This preserves tier-based spread.
        for attr, (min_bonus, max_bonus) in archetype_data.get("attributes", {}).items():
            if hasattr(player, attr):
                # The tuple values indicate how strongly this archetype favors the attr.
                # Higher max = stronger signature. Scale to a modest +2/+7 bonus.
                strength = (min_bonus + max_bonus) / 2  # 1-100 scale avg, ~56-80
                # Normalize: 56 -> +2, 80 -> +7
                bonus_mid = 2 + (strength - 56) / 24 * 5
                bonus = int(random.gauss(bonus_mid, 1.5))
                bonus = max(0, min(8, bonus))
                current_value = getattr(player, attr)
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
    
    def determine_contract_info(self, player: Player, skill_tier: str,
                                season_year=None) -> Tuple[int, int, bool, int]:
        """Determine appropriate contract salary and length for a player.

        season_year: the signing season for CBA money (league minimum /
        ELC max). When None the current season is used. Callers that know
        the league season (e.g. ELC auto-sign) should pass it -- the new
        CBA minimum escalates by season, so a default-year floor can come
        in under the signing season's floor and fail validation.

        Returns (nhl_salary, years, two_way, ahl_salary). Category logic is
        Caleb's original: ELC / bridge for the kids, superstar/premium by
        overall, veteran deals for the 33+ crowd, AHL money for minor
        leaguers, standard for everyone else.
        """
        overall = player.overall_rating()
        age = player.age

        # Determine contract category (overall on the native 100-point scale).
        # Caleb's tier structure, with star thresholds calibrated to the
        # generated curve (median 78) and the 2026 summer market: 95+ is a
        # franchise player (the Kaprizov/Celebrini/McDavid tier -- 22 in
        # the league), 90+ a first-line star (the Draisaitl/Matthews/
        # MacKinnon/Eichel tier). Kids sign entry-level deals regardless
        # of rating -- a 21-year-old stud is still on his ELC in real life.
        # The gate is the real 3/2/1 signing-age table (CBA 9.1(b)):
        # 24-and-under first-SPC signers are Group 1; 25+ is not
        # ELC-eligible at all (the new CBA removed the old European
        # 25-27 exception).
        try:
            from salary_cap_system import elc_years_for_age as _elc_yrs
            _entry_years = _elc_yrs(age)
        except Exception:
            _entry_years = 3 if age <= 21 else (2 if age <= 23 else 0)
        if _entry_years > 0:
            contract_type = "ENTRY_LEVEL"
        elif overall >= 95:
            contract_type = "SUPERSTAR"
        elif overall >= 90:
            contract_type = "PREMIUM"
        elif age <= 25 and overall < 80:
            contract_type = "BRIDGE"
        elif age >= 33 and overall < 84:
            contract_type = "VETERAN"
        elif "AHL" in skill_tier:
            contract_type = "AHL"
        else:
            contract_type = "STANDARD"

        contract_info = CONTRACT_VALUES[contract_type]

        if contract_type == "ENTRY_LEVEL":
            # New CBA (2026): the ELC band is dynamic. The floor is the
            # signing-season league minimum ($850k in 2026-27, rising to
            # $1M by 2029-30). The ceiling is the 9.3(a) max annual
            # compensation for the signing season (league minimum +
            # $175k: $1.025M in 2026-27). Term follows the real
            # signing-age table: 3 years at 18-21, 2 at 22-23, 1 at 24
            # (only ages that reach this gate are <= 24).
            try:
                from salary_cap_system import league_minimum_salary as _lms
                from salary_cap_system import elc_max_salary as _elcmax
                _elc_years = [max(1, int(_entry_years))]
                _elc_floor = int(_lms(season_year))
                _elc_ceil = int(_elcmax(_elc_years[0], season_year))
                contract_info = {
                    "min": _elc_floor,
                    "max": max(_elc_floor, _elc_ceil),
                    "years": _elc_years,
                }
            except Exception:
                pass

        # Calculate salary based on overall rating. Star tiers normalize
        # within their own overall band so franchise players spread across
        # the gate instead of all pinning at the max.
        if contract_type == "SUPERSTAR":
            salary_factor = (overall - 94) / 6
        elif contract_type == "PREMIUM":
            salary_factor = (overall - 89) / 6
        else:
            salary_factor = (overall - 62) / 28  # Normalize to 0-1 range
        salary_factor = max(0, min(1, salary_factor))

        salary_range = contract_info["max"] - contract_info["min"]
        base_salary = contract_info["min"] + (salary_range * salary_factor)

        # Add some randomness
        variation = random.uniform(0.85, 1.15)
        final_salary = int(base_salary * variation)

        # Above-market inflation: bidding wars push a share of star deals
        # past the gate, the way real mega-deals inflate the whole market.
        if contract_type in ("PREMIUM", "SUPERSTAR") and random.random() < ABOVE_MARKET_SHARE:
            bump_range = (ABOVE_MARKET_BUMP_STAR if contract_type == "SUPERSTAR"
                          else ABOVE_MARKET_BUMP)
            bump = random.uniform(*bump_range)
            final_salary = int(final_salary * bump)

        # Ensure within bounds
        ceiling = ABOVE_MARKET_CEILING if contract_type in ("PREMIUM", "SUPERSTAR") else contract_info["max"]
        final_salary = max(contract_info["min"], min(ceiling, final_salary))

        # Round to nearest 25k
        final_salary = round(final_salary / 25000) * 25000

        # Contract length
        contract_length = random.choice(contract_info["years"])

        # Two-way structure: kids and minor-leaguers sign two-way deals.
        # Everyone else is one-way.
        two_way = contract_type in ("ENTRY_LEVEL", "BRIDGE", "AHL")
        ahl_salary = 0
        if two_way:
            ahl_info = CONTRACT_VALUES["AHL"]
            ahl_range = ahl_info["max"] - ahl_info["min"]
            ahl_factor = max(0, min(1, (overall - 55) / 30))
            ahl_salary = round((ahl_info["min"] + ahl_range * ahl_factor) / 5000) * 5000
            if contract_type == "AHL":
                # Career minor-leaguer: the tier money IS the minor-league
                # pay; the NHL salary is league minimum for call-up
                # accounting.
                ahl_salary = final_salary
                try:
                    from salary_cap_system import league_minimum_salary as _lms2
                    final_salary = int(_lms2())
                except Exception:
                    final_salary = 775000
            elif contract_type == "ENTRY_LEVEL":
                # New CBA: ELC two-way minors pay caps at the 9.4 limit
                # for the prospect's draft year ($87.5k for 2026/27).
                try:
                    from salary_cap_system import elc_minor_salary_max as _emx
                    ahl_salary = min(ahl_salary, _emx())
                except Exception:
                    ahl_salary = min(ahl_salary, 87500)

        return final_salary, contract_length, two_way, ahl_salary
    
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

        # Multi-position versatility (Muck 2026-10-02): some players can play
        # a secondary position. Shown in UI as e.g. "C/LW".
        try:
            from game_classes import PlayerPosition as _PP
            _roll = random.random()
            if position == _PP.LEFT_WING and _roll < 0.35:
                player.secondary_positions = [_PP.RIGHT_WING]
            elif position == _PP.RIGHT_WING and _roll < 0.35:
                player.secondary_positions = [_PP.LEFT_WING]
            elif position == _PP.CENTER and _roll < 0.25:
                player.secondary_positions = [random.choice([_PP.LEFT_WING, _PP.RIGHT_WING])]
            elif position == _PP.LEFT_DEFENSE and _roll < 0.30:
                player.secondary_positions = [_PP.RIGHT_DEFENSE]
            elif position == _PP.RIGHT_DEFENSE and _roll < 0.30:
                player.secondary_positions = [_PP.LEFT_DEFENSE]
        except Exception:
            pass

        # Apply attributes to player
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

        # Infer traits from final attributes (Big Hitter, Speedster, etc.)
        try:
            from player_traits import infer_traits
            player.traits = infer_traits(player)
        except Exception:
            player.traits = []

        # Goalie personality: temperament + the rare generational fast-track.
        # Goalies develop differently than skaters (see
        # player_development_system), but a small chance of a generational
        # prospect can jump into an NHL role by fate.
        try:
            if player.primary_position == PlayerPosition.GOALIE:
                from goalie_personality import assign_goalie_temperament
                assign_goalie_temperament(player)
                # The fate roll: a small chance for an elite-potential goalie
                # prospect to be generational -- the Price/Fleury fast-track
                # that jumps into an NHL role instead of the slow goalie curve.
                _pot = str(getattr(player, "potential_grade",
                                   getattr(player, "true_potential_grade", "")) or "")
                _tier = _pot[:2].strip() if len(_pot) >= 2 else _pot[:1]
                if _tier in ("A+", "A", "A-"):
                    _fate_roll = 0.08
                elif _tier in ("B+", "B", "B-"):
                    _fate_roll = 0.03
                else:
                    _fate_roll = 0.0
                if _fate_roll and random.random() < _fate_roll:
                    player.generational_goalie = True
        except Exception:
            pass
        
        # Set contract info if not free agent
        if team_name != "Free Agent":
            salary, contract_length, two_way, ahl_salary = self.determine_contract_info(player, skill_tier)
            player.contract.salary = salary
            player.contract.years_remaining = contract_length
            player.contract.two_way = two_way
            player.contract.ahl_salary = ahl_salary
        
        # Set some additional properties
        player.shooting_tendency = random.randint(30, 70)
        player.hitting_tendency = random.randint(30, 70)
        # Career NHL games: age-plausible service time, not a dice roll.
        # A 20-year-old cannot have 800 NHL games. Young players start
        # near zero and accrue real games (see _credit_nhl_games_played);
        # veterans arrive with a believable history. Drives waiver
        # exemption (same table as database_generator's post-pass).
        if age <= 20:
            player.nhl_games_played = 0
        elif age <= 22:
            player.nhl_games_played = random.randint(0, (age - 20) * 60)
        else:
            _seasons = age - 21
            _per = random.randint(40, 78)
            if random.random() < 0.25:
                _per = random.randint(5, 30)  # fringe / late-bloomer
            player.nhl_games_played = min(1400, _seasons * _per)

        # Deal a locked personality blend: identity is forever, volatility
        # is scenario. The blend gives every generated batch a real mix of
        # drama, temper, and difficulty instead of one flat type.
        try:
            import reputation_system as _rs
            _rs.deal_generation_blend(player)
        except Exception:
            pass

        # Elite forward finishing floor (2026-10-02, per Muck): NHL_ELITE
        # forwards must have 80+ base finishing composite. The harmonic
        # blend punishes low attributes, so we bump the weakest finishing
        # attributes until the composite hits 80. Never touches the
        # finishing formula itself (protected lever) -- only the inputs.
        try:
            from game_classes import PlayerPosition as _PP
            if (skill_tier == "NHL_ELITE" and
                    player.primary_position in (_PP.CENTER, _PP.LEFT_WING, _PP.RIGHT_WING)):
                from attribute_composites import raw_composite as _rc
                _fin_attrs = [
                    "shooting_accuracy", "composure", "hockey_iq",
                    "offensive_positioning", "off_the_puck", "anticipation",
                    "pressure_player", "deflections", "balance", "strength",
                    "determination", "aggressiveness",
                    "wristshot", "slapshot", "one_timer", "backhand",
                ]
                for _iter in range(25):
                    try:
                        _fin = _rc(player, "finishing")
                    except Exception:
                        break
                    if _fin >= 80:
                        break
                    # Find the lowest finishing attribute and bump it
                    _lowest = None
                    _lowest_val = 999
                    for _attr in _fin_attrs:
                        try:
                            _v = float(getattr(player, _attr, 50))
                        except Exception:
                            continue
                        if _v < _lowest_val:
                            _lowest_val = _v
                            _lowest = _attr
                    if _lowest is None:
                        break
                    try:
                        setattr(player, _lowest, min(99, int(getattr(player, _lowest, 50)) + 4))
                    except Exception:
                        break
        except Exception:
            pass

        # Archetype signature floors (2026-10-02, per Muck): each archetype's
        # KEY composites follow the same pattern as the finishing floor --
        # elite (NHL_ELITE tier) hits 80+, generational (A+ potential) hits
        # 85+. A Sniper's finishing, a Playmaker's chance creation, a
        # shutdown D's defensive play. Never touches composite formulas
        # (protected levers) -- only attribute inputs.
        #
        # Busts preserved (Muck 2026-10-02): the generational floors are the
        # BEST-CASE ceiling, not a guarantee. Prospects (age < 23) get NO
        # generation floor -- they must earn 85+ through development, and a
        # bad situation means they bust and never get there. Established
        # players (23+) are proven: the floor applies.
        try:
            from player_archetypes import signature_composites as _sigs
            from attribute_composites import bump_composite_to_floor as _bump
            _pot_gs = str(getattr(player, "true_potential_grade", "") or
                          getattr(player, "potential_grade", "") or "")
            _is_gen = _pot_gs.strip().upper().startswith("A+")
            _sigs_list = _sigs(player) or []
            if skill_tier == "NHL_ELITE" and _sigs_list:
                for _comp in _sigs_list:
                    try:
                        _bump(player, _comp, 80)
                    except Exception:
                        pass
            if _is_gen and age >= 23 and _sigs_list:
                for _comp in _sigs_list:
                    try:
                        _bump(player, _comp, 85, max_iter=80, step=5)
                    except Exception:
                        pass
        except Exception:
            pass

        # Generational overall floor (2026-10-02, per Muck): players with
        # generational (A+) potential must be 85+ overall. Bump the weakest
        # overall-contributing attributes until the composite hits 85. Never
        # touches the overall formula itself (protected lever) -- only the
        # inputs. Mirrors the elite-forward finishing floor above.
        #
        # Busts preserved: prospects (age < 23) get NO floor -- the 85 is
        # their best-case development target, not a birthright.
        try:
            from game_classes import PlayerPosition as _PPG
            _pot_g = str(getattr(player, "true_potential_grade", "") or
                         getattr(player, "potential_grade", "") or "")
            if _pot_g.strip().upper().startswith("A+") and age >= 23:
                _pos_g = player.primary_position
                if _pos_g == _PPG.GOALIE:
                    _ovr_attrs = [
                        "goaltending", "reflexes", "positioning",
                        "rebound_control", "puck_handling", "glove_hand",
                        "stick_side", "breakaway_skill", "confidence",
                        "focus", "composure",
                    ]
                elif _pos_g == _PPG.CENTER:
                    _ovr_attrs = [
                        "skating", "shooting", "shooting_accuracy",
                        "shooting_power", "passing", "passing_accuracy",
                        "passing_creativity", "deking", "stickhandling",
                        "vision", "hockey_iq", "offensive_awareness",
                        "defensive_awareness", "faceoffs", "faceoff_wins",
                        "composure", "endurance", "determination",
                        "off_the_puck", "one_timer", "loose_puck",
                    ]
                elif _pos_g in (_PPG.LEFT_WING, _PPG.RIGHT_WING):
                    _ovr_attrs = [
                        "skating", "shooting", "shooting_accuracy",
                        "shooting_power", "wristshot", "slapshot", "passing",
                        "passing_accuracy", "passing_creativity", "deking",
                        "stickhandling", "vision", "hockey_iq",
                        "offensive_awareness", "defensive_awareness",
                        "composure", "endurance", "determination",
                        "off_the_puck", "one_timer", "backhand",
                        "screen_shots",
                    ]
                else:
                    _ovr_attrs = [
                        "skating", "passing", "passing_accuracy",
                        "passing_creativity", "strength", "checking",
                        "bodycheck", "defensive_awareness", "shot_blocking",
                        "pokecheck", "anticipation", "hockey_iq", "composure",
                        "aggressiveness", "balance", "endurance",
                        "determination", "slapshot", "loose_puck",
                        "pressure_player",
                    ]
                for _iter in range(30):
                    try:
                        _ovr = player.overall_rating()
                    except Exception:
                        break
                    if _ovr >= 85:
                        break
                    # Find the lowest overall-contributing attribute and bump it
                    _lowest = None
                    _lowest_val = 999
                    for _attr in _ovr_attrs:
                        try:
                            _v = float(getattr(player, _attr, 50))
                        except Exception:
                            continue
                        if _v < _lowest_val:
                            _lowest_val = _v
                            _lowest = _attr
                    if _lowest is None:
                        break
                    try:
                        setattr(player, _lowest,
                                min(99, int(getattr(player, _lowest, 50)) + 4))
                    except Exception:
                        break
        except Exception:
            pass

        # Base reputation by tier (Muck 2026-10-02): stars arrive famous,
        # depth guys arrive known, prospects arrive unknown. The existing
        # reputation dynamics build/drift from here -- never from 0.
        try:
            _tier_rep = {
                "NHL_ELITE": (75, 92),
                "NHL_STARTER": (50, 70),
                "NHL_DEPTH": (25, 45),
                "AHL_VETERAN": (15, 30),
                "AHL_PROSPECT": (5, 15),
                "JUNIOR_ELITE": (5, 15),
                "JUNIOR_PROSPECT": (0, 8),
                "INTERNATIONAL": (20, 50),
                "COLLEGE": (0, 10),
            }
            _lo, _hi = _tier_rep.get(skill_tier, (10, 25))
            _rep = random.randint(_lo, _hi)
            # Generational potential arrives with hype.
            _pot = str(getattr(player, "potential_grade", "") or "")
            _ptier = _pot[:2].strip() if len(_pot) >= 2 else _pot[:1]
            if _ptier in ("A+", "A"):
                _rep = min(95, _rep + 15)
            elif _ptier == "A-":
                _rep = min(90, _rep + 8)
            # Veterans have had time to build a name.
            if age >= 32:
                _rep = min(95, _rep + 5)
            player.reputation = max(0, min(100, int(_rep)))
            player.reputation_history = [int(player.reputation)]
        except Exception:
            pass

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
    print(f"Generated: {test_player.full_name}, {test_player.age} years old, {position_label(test_player)}")
    print(f"Overall: {test_player.overall_rating()}, Potential: {test_player.potential_grade}")
    print(f"Team: {test_player.team_name}, Salary: ${test_player.contract.salary:,}")
    
    # Test rookie class generation
    print("\nTesting rookie class generation...")
    rookies = generator.generate_rookie_class(50)
    print(f"Top 5 rookies:")
    for i, rookie in enumerate(rookies[:5]):
        print(f"{i+1}. {rookie.full_name} ({position_label(rookie)}) - {rookie.overall_rating()} OVR")
