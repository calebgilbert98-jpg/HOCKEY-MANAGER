# draft_generator.py
# Creates a new class of draft-eligible players with realistic archetypes and tiered potential.

import random
import math
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Callable, Union
from game_classes import Player, PlayerPosition, GameBalance

# --- Constants for Data Generation ---
# Using larger name pools makes for a more diverse game world.
FIRST_NAMES = {
    "Canada": ["Aiden", "Liam", "Noah", "Logan", "Ethan", "Jacob", "Nathan", "Connor", "William", "Jack", "Owen", "Ryan", "Matty", "Shane", "Brandt", "Cole", "Mason", "Lucas", "Isaac", "Dylan"],
    "USA": ["Jackson", "Wyatt", "Carter", "Luke", "Brady", "Blake", "Hunter", "Zach", "Tyler", "Brock", "Chase", "Austin", "Cody", "Seth", "Trevor", "Jake", "Jeremy", "Cam", "Johnny", "Brady"],
    "Sweden": ["Erik", "Oscar", "Elias", "Anton", "Oliver", "William", "Filip", "Gustav", "Victor", "Emil", "Rasmus", "Lucas", "Nils", "Simon", "Marcus", "Joel", "Adam", "Jakob", "Linus", "Hampus"],
    "Finland": ["Mikko", "Kaapo", "Patrik", "Joonas", "Lauri", "Aleksi", "Ville", "Juuso", "Eero", "Eetu", "Valtteri", "Miro", "Juha", "Janne", "Teuvo", "Sami", "Jari", "Artturi", "Jesse", "Kasperi"],
    "Russia": ["Andrei", "Sergei", "Vladimir", "Alexander", "Ivan", "Dmitri", "Mikhail", "Nikita", "Evgeni", "Pavel", "Maxim", "Yuri", "Igor", "Kirill", "Fyodor", "Ilya", "Artem", "Slava", "Vasili", "Denis"],
    "Czech": ["Jakub", "Jan", "Tomáš", "David", "Pavel", "Martin", "Filip", "Petr", "Jiří", "Dominik", "Radek", "Marek", "Michal", "Lukáš", "Josef", "Roman", "Ondrej", "Daniel", "Karel", "Miroslav"],
    "Other": ["Juraj", "Marco", "Leon", "Darnell", "Nico", "Moritz", "Nino", "Timo", "Kevin", "Rafael", "Dominik", "Christoph", "Manuel", "David", "Thomas", "Marco", "Anze", "Jonas", "Mats", "Leo"]
}

LAST_NAMES = {
    "Canada": ["Smith", "Brown", "Wilson", "Campbell", "Thompson", "MacDonald", "Clark", "Johnston", "Wright", "Dubois", "Roy", "Dube", "Lavoie", "Gagnon", "Bouchard", "Leblanc", "Gauthier", "Poulin", "Morin", "Cote"],
    "USA": ["Johnson", "Miller", "Williams", "Jones", "Brown", "Davis", "Anderson", "Wilson", "Taylor", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Robinson", "Lewis", "Walker", "Young", "Allen"],
    "Sweden": ["Andersson", "Karlsson", "Nilsson", "Eriksson", "Larsson", "Olsson", "Lindqvist", "Petersson", "Svensson", "Gustafsson", "Lundqvist", "Nyquist", "Hedman", "Ekman-Larsson", "Hörnqvist", "Bäckström", "Silfverberg", "Zetterberg", "Hjalmarsson", "Ekholm"],
    "Finland": ["Koivu", "Laine", "Rantanen", "Ristolainen", "Lindell", "Barkov", "Granlund", "Haula", "Donskoi", "Armia", "Nieminen", "Lehkonen", "Heiskanen", "Lankinen", "Rinne", "Rask", "Saros", "Heinola", "Teravainen", "Kakko"],
    "Russia": ["Ovechkin", "Malkin", "Kuznetsov", "Tarasenko", "Kucherov", "Vasilevskiy", "Bobrovsky", "Panarin", "Svechnikov", "Zadorov", "Provorov", "Zaitsev", "Orlov", "Podkolzin", "Romanov", "Kaprizov", "Kravtsov", "Shesterkin", "Sorokin", "Askarov"],
    "Czech": ["Nečas", "Palát", "Voráček", "Krejčí", "Kaše", "Zadina", "Hronek", "Chytil", "Jaškin", "Faksa", "Zacha", "Polák", "Gudas", "Radil", "Simon", "Nosek", "Frk", "Šustr", "Rutta", "Jeřábek"],
    "Other": ["Kopitar", "Josi", "Niederreiter", "Ehlers", "Meier", "Hischier", "Fiala", "Draisaitl", "Kahun", "Sturm", "Greiss", "Raffl", "Grabner", "Vanek", "Zuccarello", "Fasth", "Diaz", "Sbisa", "Streit", "Hansen"]
}

BIRTHPLACES = {
    "Canada": [
        "Toronto, ON", "Montreal, QC", "Vancouver, BC", "Calgary, AB", "Edmonton, AB", 
        "Winnipeg, MB", "Ottawa, ON", "Halifax, NS", "Quebec City, QC", "Mississauga, ON",
        "London, ON", "Kelowna, BC", "Regina, SK", "Saskatoon, SK", "Thunder Bay, ON"
    ],
    "USA": [
        "Boston, MA", "Chicago, IL", "Minneapolis, MN", "Detroit, MI", "Buffalo, NY", 
        "St. Paul, MN", "New York, NY", "Grand Forks, ND", "Pittsburgh, PA", "Anchorage, AK",
        "Madison, WI", "Ann Arbor, MI", "St. Louis, MO", "Philadelphia, PA", "Las Vegas, NV"
    ],
    "Sweden": [
        "Stockholm", "Gothenburg", "Malmo", "Uppsala", "Linkoping", 
        "Vasteras", "Orebro", "Umea", "Lulea", "Karlstad"
    ],
    "Finland": [
        "Helsinki", "Tampere", "Turku", "Espoo", "Vantaa", 
        "Oulu", "Jyvaskyla", "Kuopio", "Lahti", "Pori"
    ],
    "Russia": [
        "Moscow", "St. Petersburg", "Chelyabinsk", "Magnitogorsk", "Yaroslavl", 
        "Yekaterinburg", "Omsk", "Novosibirsk", "Kazan", "Ufa"
    ],
    "Czech": [
        "Prague", "Brno", "Ostrava", "Kladno", "Plzen", 
        "Liberec", "Olomouc", "Pardubice", "Zlin", "Karlovy Vary"
    ],
    "Other": [
        "Bratislava, SVK", "Vienna, AUT", "Bern, CHE", "Zurich, CHE", "Berlin, DEU", 
        "Munich, DEU", "Cologne, DEU", "Ljubljana, SVN", "Oslo, NOR", "Copenhagen, DNK"
    ]
}

# --- Player Archetypes ---
# Defines the attribute ranges for different player types. This makes balancing easier.
ARCHETYPES = {
    "FORWARDS": {
        "Sniper": {
            "description": "An elite goal-scorer with exceptional shooting skills",
            "attributes": {
                "shooting": (14, 20), 
                "offensive_awareness": (12, 18), 
                "deking": (11, 17),
                "shooting_accuracy": (14, 20),
                "vision": (10, 16)
            },
            "tendency": {"shooting_tendency": (70, 90), "hitting_tendency": (20, 50)}
        },
        "Playmaker": {
            "description": "A creative passer who excels at setting up teammates",
            "attributes": {
                "passing": (14, 20), 
                "vision": (13, 19), 
                "offensive_awareness": (12, 17),
                "puck_control": (12, 17),
                "deking": (11, 16)
            },
            "tendency": {"shooting_tendency": (20, 40), "hitting_tendency": (10, 40)}
        },
        "Power Forward": {
            "description": "A physical forward who combines size with scoring ability",
            "attributes": {
                "strength": (14, 19), 
                "checking": (13, 18), 
                "shooting": (11, 16),
                "stamina": (12, 17),
                "puck_protection": (12, 17)
            },
            "tendency": {"shooting_tendency": (50, 70), "hitting_tendency": (70, 90)}
        },
        "Two-Way Forward": {
            "description": "A balanced player who contributes at both ends of the ice",
            "attributes": {
                "defensive_awareness": (13, 17), 
                "teamwork": (12, 17), 
                "faceoffs": (10, 16),
                "skating": (11, 16),
                "discipline": (12, 16)
            },
            "tendency": {"shooting_tendency": (40, 60), "hitting_tendency": (40, 60)}
        },
        "Grinder": {
            "description": "A hard-working, physical player who excels along the boards",
            "attributes": {
                "determination": (13, 18), 
                "strength": (12, 17), 
                "checking": (12, 17),
                "puck_protection": (11, 16),
                "stamina": (13, 17)
            },
            "tendency": {"shooting_tendency": (30, 50), "hitting_tendency": (60, 90)}
        },
        "Skilled Finesse": {
            "description": "A highly skilled player with exceptional stickhandling",
            "attributes": {
                "deking": (14, 19), 
                "puck_control": (13, 18), 
                "flair": (13, 18),
                "skating": (12, 17),
                "vision": (11, 16)
            },
            "tendency": {"shooting_tendency": (40, 70), "hitting_tendency": (10, 30)}
        }
    },
    "DEFENSEMEN": {
        "Offensive Defenseman": {
            "description": "A mobile defenseman who contributes offensively",
            "attributes": {
                "skating": (13, 18), 
                "passing": (12, 17), 
                "offensive_awareness": (12, 16),
                "shooting": (11, 16),
                "vision": (10, 16)
            },
            "tendency": {"shooting_tendency": (50, 70), "hitting_tendency": (30, 60)}
        },
        "Defensive Defenseman": {
            "description": "A stay-at-home defender who excels in his own zone",
            "attributes": {
                "checking": (13, 18), 
                "strength": (12, 17), 
                "defensive_awareness": (13, 18),
                "discipline": (11, 16),
                "shot_blocking": (12, 17)
            },
            "tendency": {"shooting_tendency": (20, 40), "hitting_tendency": (60, 80)}
        },
        "Two-Way Defenseman": {
            "description": "A balanced defender who contributes at both ends",
            "attributes": {
                "defensive_awareness": (12, 16), 
                "skating": (11, 16), 
                "passing": (10, 15),
                "checking": (11, 16),
                "shot_blocking": (11, 16)
            },
            "tendency": {"shooting_tendency": (30, 60), "hitting_tendency": (40, 70)}
        },
        "Physical Defenseman": {
            "description": "An intimidating defender who plays a punishing style",
            "attributes": {
                "strength": (14, 19), 
                "checking": (13, 18), 
                "shot_blocking": (12, 17),
                "stamina": (11, 16),
                "discipline": (8, 13)
            },
            "tendency": {"shooting_tendency": (20, 40), "hitting_tendency": (70, 90)}
        },
        "Puck-Moving Defenseman": {
            "description": "A defender who excels at transitioning the puck",
            "attributes": {
                "passing": (13, 18), 
                "puck_control": (12, 17), 
                "vision": (12, 17),
                "skating": (12, 17),
                "defensive_awareness": (10, 15)
            },
            "tendency": {"shooting_tendency": (30, 50), "hitting_tendency": (20, 50)}
        }
    },
    "GOALIES": {
        "Butterfly Goalie": {
            "description": "A technical goalie who excels at covering the lower net",
            "attributes": {
                "goaltending": (12, 18), 
                "reflexes": (11, 17),
                "positioning": (12, 18),
                "rebound_control": (10, 16),
                "puck_handling": (7, 14)
            }
        },
        "Hybrid Goalie": {
            "description": "A versatile goalie who combines different styles",
            "attributes": {
                "goaltending": (12, 17), 
                "reflexes": (12, 17),
                "positioning": (11, 16),
                "rebound_control": (11, 16),
                "puck_handling": (10, 15)
            }
        },
        "Athletic Goalie": {
            "description": "A dynamic goalie who relies on athleticism and reflexes",
            "attributes": {
                "goaltending": (11, 16), 
                "reflexes": (14, 19),
                "positioning": (10, 15),
                "rebound_control": (9, 14),
                "puck_handling": (9, 15)
            }
        },
        "Puck-Handling Goalie": {
            "description": "A goalie who excels at playing the puck",
            "attributes": {
                "goaltending": (11, 16), 
                "reflexes": (10, 16),
                "positioning": (11, 16),
                "rebound_control": (10, 15),
                "puck_handling": (14, 19)
            }
        }
    }
}

# --- League and Draft Settings ---
COUNTRY_DISTRIBUTION = {
    "Canada": 0.45,   # 45% of players
    "USA": 0.25,      # 25% of players
    "Sweden": 0.08,   # 8% of players  
    "Finland": 0.05,  # 5% of players
    "Russia": 0.05,   # 5% of players
    "Czech": 0.04,    # 4% of players
    "Other": 0.08     # 8% of players
}

POSITION_DISTRIBUTION = {
    PlayerPosition.CENTER: 0.25,
    PlayerPosition.LEFT_WING: 0.15,
    PlayerPosition.RIGHT_WING: 0.15,
    PlayerPosition.LEFT_DEFENSE: 0.15,
    PlayerPosition.RIGHT_DEFENSE: 0.15,
    PlayerPosition.GOALIE: 0.15
}

# --- Potential Distribution ---
POTENTIAL_DISTRIBUTION = {
    # Elite talent
    "A+": 0.005,  # 0.5% - Generational talent 
    "A": 0.015,   # 1.5% - Elite talent
    "A-": 0.03,   # 3.0% - Top-line talent
    
    # Good talent
    "B+": 0.05,   # 5.0% - Top-six/top-four talent
    "B": 0.10,    # 10.0% - Top-six/top-four talent
    "B-": 0.15,   # 15.0% - Middle-six/top-six talent
    
    # Average talent
    "C+": 0.15,   # 15.0% - Middle-six/bottom-four talent
    "C": 0.20,    # 20.0% - Bottom-six/bottom-pair talent
    "C-": 0.15,   # 15.0% - Fringe NHL talent
    
    # Below average talent
    "D": 0.10,    # 10.0% - AHL talent with limited NHL upside
    "F": 0.05     # 5.0% - Minor league talent
}

# Attribute development profiles based on potential
DEVELOPMENT_PROFILES = {
    "A+": {"peak_age": 25, "development_speed": 1.5, "ceiling_modifier": 1.3},
    "A": {"peak_age": 26, "development_speed": 1.4, "ceiling_modifier": 1.25},
    "A-": {"peak_age": 26, "development_speed": 1.3, "ceiling_modifier": 1.2},
    "B+": {"peak_age": 26, "development_speed": 1.2, "ceiling_modifier": 1.15},
    "B": {"peak_age": 27, "development_speed": 1.1, "ceiling_modifier": 1.1},
    "B-": {"peak_age": 27, "development_speed": 1.0, "ceiling_modifier": 1.05},
    "C+": {"peak_age": 28, "development_speed": 0.9, "ceiling_modifier": 1.0},
    "C": {"peak_age": 28, "development_speed": 0.8, "ceiling_modifier": 0.95},
    "C-": {"peak_age": 29, "development_speed": 0.7, "ceiling_modifier": 0.9},
    "D": {"peak_age": 30, "development_speed": 0.6, "ceiling_modifier": 0.85},
    "F": {"peak_age": 31, "development_speed": 0.5, "ceiling_modifier": 0.8}
}

def get_random_nationality(weighted=True) -> str:
    """Returns a randomly selected nationality based on probability distribution."""
    if weighted:
        countries = list(COUNTRY_DISTRIBUTION.keys())
        probabilities = list(COUNTRY_DISTRIBUTION.values())
        return random.choices(countries, weights=probabilities, k=1)[0]
    else:
        return random.choice(list(COUNTRY_DISTRIBUTION.keys()))
        
def get_random_name(country: str) -> Tuple[str, str]:
    """Returns a random first and last name appropriate for the given country."""
    first_name = random.choice(FIRST_NAMES.get(country, FIRST_NAMES["Other"]))
    last_name = random.choice(LAST_NAMES.get(country, LAST_NAMES["Other"]))
    return first_name, last_name

def get_random_birthplace(country: str) -> str:
    """Returns a random birthplace for the given country."""
    return random.choice(BIRTHPLACES.get(country, BIRTHPLACES["Other"]))

def get_random_position(weighted=True) -> PlayerPosition:
    """Returns a randomly selected position based on probability distribution."""
    if weighted:
        positions = list(POSITION_DISTRIBUTION.keys())
        probabilities = list(POSITION_DISTRIBUTION.values())
        return random.choices(positions, weights=probabilities, k=1)[0]
    else:
        return random.choice(list(PlayerPosition))

def get_random_potential() -> str:
    """Returns a randomly selected potential grade based on probability distribution."""
    potentials = list(POTENTIAL_DISTRIBUTION.keys())
    probabilities = list(POTENTIAL_DISTRIBUTION.values())
    return random.choices(potentials, weights=probabilities, k=1)[0]

def get_archetype_for_position(position: PlayerPosition) -> Tuple[str, dict]:
    """Returns a random archetype appropriate for the given position."""
    if position in [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]:
        category = "FORWARDS"
    elif position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]:
        category = "DEFENSEMEN"
    else:  # Goalie
        category = "GOALIES"
        
    archetype_name = random.choice(list(ARCHETYPES[category].keys()))
    return archetype_name, ARCHETYPES[category][archetype_name]

def get_base_attribute_value(min_val: int = 5, max_val: int = 15) -> int:
    """
    Generate a base attribute value following a normal distribution.
    Most values will be around the middle of the range.
    """
    mean = (min_val + max_val) / 2
    std_dev = (max_val - min_val) / 4  # This gives a reasonable spread
    value = int(random.normalvariate(mean, std_dev))
    return max(min_val, min(max_val, value))

def calculate_draft_ranking(player: Player) -> float:
    """Calculate a draft ranking score for a player based on attributes and potential."""
    # Convert potential grade to numeric value
    potential_values = {
        "A+": 100, "A": 95, "A-": 90,
        "B+": 85, "B": 80, "B-": 75,
        "C+": 70, "C": 65, "C-": 60,
        "D": 50, "F": 40
    }
    potential_value = potential_values.get(player.potential_grade, 65)
    
    # Get current overall rating
    current_rating = player.overall_rating()
    
    # Calculate ranking score with some randomness
    ranking_score = (current_rating * 0.7) + (potential_value * 0.3)
    
    # Add some randomness to simulate scouting variance
    ranking_score += random.uniform(-5, 5)
    
    return ranking_score

def generate_birthdate(age: int, variation_days: int = 180) -> datetime:
    """Generate a realistic birthdate for a player of the given age."""
    today = datetime.now()
    birth_year = today.year - age
    
    # Draft-eligible players are typically born between Jan 1 and Sep 15
    if age == 18:
        month = random.randint(1, 9)
        day = random.randint(1, 28)
        if month == 9:
            day = random.randint(1, 15)  # Only first half of September
    else:
        # For other ages, generate any date
        month = random.randint(1, 12)
        day = random.randint(1, 28)
    
    # Add some random variation
    variation = random.randint(-variation_days, variation_days)
    base_date = datetime(birth_year, month, day)
    return base_date + timedelta(days=variation)

def create_prospect(age: int = 18, 
                   position: Optional[PlayerPosition] = None, 
                   potential: Optional[str] = None,
                   nationality: Optional[str] = None) -> Player:
    """
    Create a new prospect with the specified parameters.
    If parameters are not provided, they will be randomly generated.
    """
    # Determine nationality if not specified
    if nationality is None:
        nationality = get_random_nationality()
    
    # Get a name appropriate for the nationality
    first_name, last_name = get_random_name(nationality)
    birthplace = get_random_birthplace(nationality)
    
    # Determine position if not specified
    if position is None:
        position = get_random_position()
    
    # Determine potential if not specified
    if potential is None:
        potential = get_random_potential()
    
    # Get an appropriate archetype for the position
    archetype_name, archetype_data = get_archetype_for_position(position)
    
    # Create the player with basic info
    player = Player(
        first_name=first_name,
        last_name=last_name,
        age=age,
        primary_position=position
    )
    
    # Set enhanced personal information
    player.birthplace = birthplace
    player.nationality = nationality
    player.potential_grade = potential
    
    # Generate realistic physical attributes for prospects
    if position == PlayerPosition.GOALIE:
        # Young goalies, typically taller
        feet = random.choices([5, 6], weights=[15, 85])[0]
        inches = random.randint(9, 11) if feet == 5 else random.randint(0, 4)
        player.height = f"{feet}'{inches}\""
        player.weight = random.randint(170, 200)  # Younger, less filled out
    elif position in [PlayerPosition.DEFENSE, PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]:
        # Young defensemen
        feet = random.choices([5, 6], weights=[25, 75])[0]
        inches = random.randint(10, 11) if feet == 5 else random.randint(0, 3)
        player.height = f"{feet}'{inches}\""
        player.weight = random.randint(165, 200)
    else:
        # Young forwards
        feet = random.choices([5, 6], weights=[35, 65])[0]
        inches = random.randint(8, 11) if feet == 5 else random.randint(0, 2)
        player.height = f"{feet}'{inches}\""
        player.weight = random.randint(155, 190)
    
    # Shooting hand for prospects
    if position == PlayerPosition.GOALIE:
        player.handedness = random.choices(["Left", "Right"], weights=[65, 35])[0]
    else:
        if nationality in ["Finland", "Sweden", "Russia"]:
            player.handedness = random.choices(["Left", "Right"], weights=[65, 35])[0]
        else:
            player.handedness = random.choices(["Left", "Right"], weights=[25, 75])[0]
    
    # Birth and draft information for prospects
    birth_year = 2024 - age
    player.birth_date = f"{birth_year}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    player.draft_year = birth_year + 18  # Eligible at 18
    player.draft_position = "Prospect"  # Will be set after draft
    
    # Career info for prospects
    player.pro_debut = "N/A"
    player.teams_count = 0
    player.team_tenure = "N/A"
    
    # Potential for prospects
    potential_mapping = {"A": random.randint(17, 20), "B": random.randint(14, 18), 
                        "C": random.randint(11, 16), "D": random.randint(8, 13), 
                        "F": random.randint(5, 10)}
    player.potential = potential_mapping.get(potential, 12)
    player.peak_rating = player.potential + random.randint(-2, 2)
    
    # Health info for prospects
    player.is_injured = False  # Prospects rarely injured in profile
    player.days_missed = 0
    player.career_games_missed = random.randint(0, 10)  # Junior hockey
    player.last_injury = random.choices(["None", "Minor injury"], weights=[85, 15])[0]
    
    # Current season stats should start at 0
    player.games_played = 0
    
    # Stats should start at 0 for new season - only set games played based on age/experience
    if position == PlayerPosition.GOALIE:
        player.wins = 0
        player.losses = 0
        player.save_percentage = 0.000
        player.goals_against_avg = 0.00
        player.shutouts = 0
    else:
        player.goals = 0
        player.assists = 0
        player.points = 0
        player.plus_minus = 0
        player.avg_toi = "0:00"
    
    # Set common attributes (every player gets these)
    for attr in ['skating', 'shooting', 'passing', 'checking', 'faceoffs', 
                'determination', 'teamwork', 'leadership', 'discipline', 'flair',
                'offensive_awareness', 'defensive_awareness', 'deking', 'strength']:
        setattr(player, attr, get_base_attribute_value(5, 12))
    
    # Set goalie-specific attributes
    if position == PlayerPosition.GOALIE:
        for attr in ['goaltending', 'reflexes', 'positioning', 'rebound_control', 'puck_handling']:
            setattr(player, attr, get_base_attribute_value(5, 12))
    
    # Set advanced attributes
    for attr in ['vision', 'puck_control', 'shooting_accuracy', 'puck_protection', 'stamina', 'shot_blocking']:
        setattr(player, attr, get_base_attribute_value(5, 12))
    
    # Set tendencies with defaults
    player.shooting_tendency = random.randint(30, 70)
    player.hitting_tendency = random.randint(30, 70)
    
    # Apply the archetype-specific attribute modifiers
    for attr, (min_val, max_val) in archetype_data.get("attributes", {}).items():
        # Get a random value in the archetype's range
        value = random.randint(min_val, max_val)
        # Apply potential-based adjustment (better potential = higher chance of good attributes)
        potential_factor = DEVELOPMENT_PROFILES[potential]["ceiling_modifier"]
        adjusted_value = int(value * potential_factor)
        # Ensure it stays within valid bounds
        adjusted_value = max(GameBalance.MIN_ATTRIBUTE, min(GameBalance.MAX_ATTRIBUTE, adjusted_value))
        # Set the attribute
        setattr(player, attr, adjusted_value)
    
    # Apply archetype-specific tendencies if available
    for tendency, (min_val, max_val) in archetype_data.get("tendency", {}).items():
        setattr(player, tendency, random.randint(min_val, max_val))
    
    # Calculate draft ranking for later sorting
    player.draft_ranking = calculate_draft_ranking(player)
    
    return player

def generate_draft_class(num_prospects: int = 224) -> list[Player]:
    """
    Generates a list of new 18-year-old players for the draft,
    with a realistic distribution of talent.
    """
    prospects = []
    
    # Ensure we have a minimum number of players at each position
    position_counts = {pos: 0 for pos in PlayerPosition}
    min_per_position = 20  # Ensure at least 20 players per position
    
    # Ensure we have a minimum number of players at each potential tier
    potential_counts = {pot: 0 for pot in POTENTIAL_DISTRIBUTION.keys()}
    
    # Generate enough prospects to meet the requested total
    while len(prospects) < num_prospects:
        # Determine if we need to force a specific position
        forced_position = None
        for pos, count in position_counts.items():
            if count < min_per_position:
                forced_position = pos
                break
        
        # Generate the prospect
        prospect = create_prospect(position=forced_position)
        
        # Update our counters
        position_counts[prospect.primary_position] += 1
        potential_counts[prospect.potential_grade] += 1
        
        # Add to our list
        prospects.append(prospect)
    
    # Sort prospects by draft ranking for convenience
    prospects.sort(key=lambda p: p.draft_ranking, reverse=True)
    
    print(f"Generated a new draft class with {len(prospects)} prospects.")
    print(f"Position distribution: {position_counts}")
    print(f"Potential distribution: {potential_counts}")
    
    return prospects

def get_scouting_info(player: Player) -> dict:
    """Returns a dictionary of information that would be available from scouting."""
    return {
        "name": player.full_name,
        "position": player.primary_position.name,
        "age": player.age,
        "nationality": player.nationality,
        "birthplace": player.birthplace,
        "draft_ranking": getattr(player, "draft_ranking", 0),
        "potential_estimate": player.potential_grade  # This would be hidden until scouted
    }
