# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# database_generator.py
# Comprehensive database generation system inspired by Eastside Hockey Manager
# Supports multiple database sizes for different levels of realism and detail

import random
from typing import (List, Dict, Optional)
from game_classes import (Player, Team, League, PlayerPosition, Contract, debug_print,
                                StaffRole)
from dataclasses import dataclass
import mesh_system

# ---------------------------------------------------------------------------
# R5 (UI repairs, expanded): staff role design.
#
# HIREABLE_STAFF_ROLES -- roles with real game value (coaches, scouts,
# analytics). These appear in the free-agent staff pool with real depth so
# hiring is actually possible.
#
# BACKGROUND_STAFF_ROLES -- physio-type support roles. They are auto-filled
# on every club (no hiring needed) and never appear in the FA pool or the
# Hire Staff flow. Their ratings still matter where read (e.g. medical
# staff feed the injury-recovery modifier in injury_data).
# ---------------------------------------------------------------------------
HIREABLE_STAFF_ROLES = (
    StaffRole.GENERAL_MANAGER,
    StaffRole.ASSISTANT_GENERAL_MANAGER,
    StaffRole.HEAD_COACH,
    StaffRole.ASSOCIATE_COACH,
    StaffRole.ASSISTANT_COACH,
    StaffRole.GOALIE_COACH,
    StaffRole.POWER_PLAY_COACH,
    StaffRole.PENALTY_KILL_COACH,
    StaffRole.VIDEO_COACH,
    StaffRole.SKILLS_COACH,
    StaffRole.SKATING_COACH,
    StaffRole.CONDITIONING_COACH,
    StaffRole.STRENGTH_COACH,
    StaffRole.HEAD_SCOUT,
    StaffRole.PROFESSIONAL_SCOUT,
    StaffRole.AMATEUR_SCOUT,
    StaffRole.EUROPEAN_SCOUT,
    StaffRole.ADVANCE_SCOUT,
    StaffRole.ANALYTICS_DIRECTOR,
)

BACKGROUND_STAFF_ROLES = (
    StaffRole.TEAM_DOCTOR,
    StaffRole.PHYSIOTHERAPIST,
    StaffRole.EQUIPMENT_MANAGER,
    StaffRole.STATISTICIAN,
    StaffRole.MEDIA_RELATIONS,
)

# R5 (UI repairs, expanded): full hockey-ops org template.
# Each entry is (role, count, base salary). Shared by new-game
# generation and the old-save backfill so they never drift.
TEAM_STAFF_TEMPLATE = [
    # Management
    (StaffRole.GENERAL_MANAGER, 1, 700_000),
    (StaffRole.ASSISTANT_GENERAL_MANAGER, 1, 300_000),
    # Coaching staff
    (StaffRole.HEAD_COACH, 1, 600_000),
    (StaffRole.ASSOCIATE_COACH, 1, 350_000),
    (StaffRole.ASSISTANT_COACH, 2, 275_000),
    (StaffRole.GOALIE_COACH, 1, 250_000),
    (StaffRole.POWER_PLAY_COACH, 1, 250_000),
    (StaffRole.PENALTY_KILL_COACH, 1, 250_000),
    (StaffRole.VIDEO_COACH, 1, 125_000),
    # Development staff
    (StaffRole.SKILLS_COACH, 1, 160_000),
    (StaffRole.SKATING_COACH, 1, 150_000),
    (StaffRole.CONDITIONING_COACH, 1, 150_000),
    (StaffRole.STRENGTH_COACH, 1, 150_000),
    # Scouting staff
    (StaffRole.HEAD_SCOUT, 1, 275_000),
    (StaffRole.PROFESSIONAL_SCOUT, 2, 125_000),
    (StaffRole.AMATEUR_SCOUT, 2, 110_000),
    (StaffRole.EUROPEAN_SCOUT, 1, 125_000),
    (StaffRole.ADVANCE_SCOUT, 1, 110_000),
    # Analytics
    (StaffRole.ANALYTICS_DIRECTOR, 1, 250_000),
    # Medical & support (background: auto-filled, never hireable)
    (StaffRole.TEAM_DOCTOR, 1, 200_000),
    (StaffRole.PHYSIOTHERAPIST, 1, 100_000),
    (StaffRole.EQUIPMENT_MANAGER, 1, 80_000),
    # Analytics & media (background: auto-filled, never hireable)
    (StaffRole.STATISTICIAN, 1, 75_000),
    (StaffRole.MEDIA_RELATIONS, 1, 90_000),
]

@dataclass
class DatabaseConfig:
    """Configuration for database generation"""
    name: str
    description: str
    total_players: int
    prospects_per_draft: int
    leagues_count: int
    teams_per_league: int
    depth_factor: float  # Multiplier for roster depth
    veteran_distribution: float  # Percentage of veteran players
    international_factor: float  # International player diversity
    minor_league_depth: int  # Number of minor league levels
    staff_count: int  # Support staff per team
    league_infos: Optional[List[dict]] = None  # Custom league list; if set, overrides LEAGUE_STRUCTURES lookup

# Database size configurations inspired by EHM
DATABASE_CONFIGURATIONS = {
    "Small": DatabaseConfig(
        name="Small Database",
        description="Quick start with essential players only. Perfect for faster gameplay and learning.",
        total_players=8000,
        prospects_per_draft=150,
        leagues_count=2,
        teams_per_league=30,
        depth_factor=0.7,
        veteran_distribution=0.6,
        international_factor=0.8,
        minor_league_depth=2,
        staff_count=8
    ),
    "Medium": DatabaseConfig(
        name="Medium Database",
        description="Balanced database with good depth and variety. Recommended for most players.",
        total_players=25000,
        prospects_per_draft=224,
        leagues_count=5,
        teams_per_league=28,
        depth_factor=1.0,
        veteran_distribution=0.7,
        international_factor=1.0,
        minor_league_depth=3,
        staff_count=15
    ),
    "Large": DatabaseConfig(
        name="Large Database",
        description="Extensive database with detailed minor leagues and international depth.",
        total_players=50000,
        prospects_per_draft=300,
        leagues_count=12,
        teams_per_league=25,
        depth_factor=1.3,
        veteran_distribution=0.75,
        international_factor=1.2,
        minor_league_depth=4,
        staff_count=20
    ),
    "Massive": DatabaseConfig(
        name="Massive Database",
        description="Ultimate realism with comprehensive global hockey representation. For dedicated managers.",
        total_players=100000,
        prospects_per_draft=450,
        leagues_count=25,
        teams_per_league=24,
        depth_factor=1.5,
        veteran_distribution=0.8,
        international_factor=1.5,
        minor_league_depth=6,
        staff_count=30
    )
}

# Real NHL team names for authentic experience (2024-25 season)
NHL_TEAMS = [
    "Boston Bruins", "Buffalo Sabres", "Detroit Red Wings", "Florida Panthers",
    "Montreal Canadiens", "Ottawa Senators", "Tampa Bay Lightning", "Toronto Maple Leafs",
    "Carolina Hurricanes", "Columbus Blue Jackets", "New Jersey Devils", "NY Islanders",
    "NY Rangers", "Philadelphia Flyers", "Pittsburgh Penguins", "Washington Capitals",
    "Utah Hockey Club", "Chicago Blackhawks", "Colorado Avalanche", "Dallas Stars",
    "Minnesota Wild", "Nashville Predators", "St. Louis Blues", "Winnipeg Jets",
    "Anaheim Ducks", "Calgary Flames", "Edmonton Oilers", "Los Angeles Kings",
    "San Jose Sharks", "Seattle Kraken", "Vancouver Canucks", "Vegas Golden Knights"
]

# NHL Team divisions and conferences (2024-25 season)
NHL_TEAM_INFO = {
    # Atlantic Division (Eastern Conference)
    "Boston Bruins": {"division": "Atlantic", "conference": "Eastern"},
    "Buffalo Sabres": {"division": "Atlantic", "conference": "Eastern"},
    "Detroit Red Wings": {"division": "Atlantic", "conference": "Eastern"},
    "Florida Panthers": {"division": "Atlantic", "conference": "Eastern"},
    "Montreal Canadiens": {"division": "Atlantic", "conference": "Eastern"},
    "Ottawa Senators": {"division": "Atlantic", "conference": "Eastern"},
    "Tampa Bay Lightning": {"division": "Atlantic", "conference": "Eastern"},
    "Toronto Maple Leafs": {"division": "Atlantic", "conference": "Eastern"},
    
    # Metropolitan Division (Eastern Conference)
    "Carolina Hurricanes": {"division": "Metropolitan", "conference": "Eastern"},
    "Columbus Blue Jackets": {"division": "Metropolitan", "conference": "Eastern"},
    "New Jersey Devils": {"division": "Metropolitan", "conference": "Eastern"},
    "NY Islanders": {"division": "Metropolitan", "conference": "Eastern"},
    "NY Rangers": {"division": "Metropolitan", "conference": "Eastern"},
    "Philadelphia Flyers": {"division": "Metropolitan", "conference": "Eastern"},
    "Pittsburgh Penguins": {"division": "Metropolitan", "conference": "Eastern"},
    "Washington Capitals": {"division": "Metropolitan", "conference": "Eastern"},
    
    # Central Division (Western Conference)
    "Chicago Blackhawks": {"division": "Central", "conference": "Western"},
    "Colorado Avalanche": {"division": "Central", "conference": "Western"},
    "Dallas Stars": {"division": "Central", "conference": "Western"},
    "Minnesota Wild": {"division": "Central", "conference": "Western"},
    "Nashville Predators": {"division": "Central", "conference": "Western"},
    "St. Louis Blues": {"division": "Central", "conference": "Western"},
    "Utah Hockey Club": {"division": "Central", "conference": "Western"},
    "Winnipeg Jets": {"division": "Central", "conference": "Western"},
    
    # Pacific Division (Western Conference)
    "Anaheim Ducks": {"division": "Pacific", "conference": "Western"},
    "Calgary Flames": {"division": "Pacific", "conference": "Western"},
    "Edmonton Oilers": {"division": "Pacific", "conference": "Western"},
    "Los Angeles Kings": {"division": "Pacific", "conference": "Western"},
    "San Jose Sharks": {"division": "Pacific", "conference": "Western"},
    "Seattle Kraken": {"division": "Pacific", "conference": "Western"},
    "Vancouver Canucks": {"division": "Pacific", "conference": "Western"},
    "Vegas Golden Knights": {"division": "Pacific", "conference": "Western"}
}

# AHL team names for realism
AHL_TEAMS = [
    "Providence Bruins", "Rochester Americans", "Grand Rapids Griffins", "Charlotte Checkers",
    "Laval Rocket", "Belleville Senators", "Syracuse Crunch", "Toronto Marlies",
    "Chicago Wolves", "Cleveland Monsters", "Utica Comets", "Bridgeport Islanders",
    "Hartford Wolf Pack", "Lehigh Valley Phantoms", "Wilkes-Barre/Scranton Penguins", "Hershey Bears",
    "Tucson Roadrunners", "Rockford IceHogs", "Colorado Eagles", "Texas Stars",
    "Iowa Wild", "Milwaukee Admirals", "Springfield Thunderbirds", "Manitoba Moose",
    "San Diego Gulls", "Calgary Wranglers", "Bakersfield Condors", "Ontario Reign",
    "San Jose Barracuda", "Coachella Valley Firebirds", "Abbotsford Canucks", "Henderson Silver Knights"
]
EXTENDED_FIRST_NAMES = {
    "Canada": ["Aiden", "Liam", "Noah", "Logan", "Ethan", "Jacob", "Nathan", "Connor", "William", "Jack", "Owen", "Ryan", "Matty", "Shane", "Brandt", "Cole", "Mason", "Lucas", "Isaac", "Dylan", "Carter", "Hunter", "Tyler", "Cameron", "Brendan", "Colton", "Garrett", "Austin", "Blake", "Brett", "Braden", "Cody", "Devon", "Dawson", "Griffin", "Jesse", "Jared", "Kyle", "Matt", "Quinn", "Reed", "Tanner", "Zach"],
    "USA": ["Jackson", "Wyatt", "Carter", "Luke", "Brady", "Blake", "Hunter", "Zach", "Tyler", "Brock", "Chase", "Austin", "Cody", "Seth", "Trevor", "Jake", "Jeremy", "Cam", "Johnny", "Brady", "Mason", "Ethan", "Connor", "Ryan", "Cole", "Alex", "Drew", "Garrett", "Logan", "Parker", "Spencer", "Trent", "Wade", "Mitchell", "Kevin", "Shane", "Derek", "Brandon", "Dustin", "Craig", "Jared", "Kyle"],
    "Sweden": ["Erik", "Oscar", "Elias", "Anton", "Oliver", "William", "Filip", "Gustav", "Victor", "Emil", "Rasmus", "Lucas", "Nils", "Simon", "Marcus", "Joel", "Adam", "Jakob", "Linus", "Hampus", "Isak", "Axel", "Hugo", "Noah", "Leo", "Theo", "Alexander", "Felix", "Wilmer", "Benjamin", "Ludvig", "Max", "Charlie", "Vincent", "Viggo", "Gabriel", "Melvin", "Melker", "Albin", "Arvid", "Sigge", "Dante"],
    "Finland": ["Mikko", "Kaapo", "Patrik", "Joonas", "Lauri", "Aleksi", "Ville", "Juuso", "Eero", "Eetu", "Valtteri", "Miro", "Juha", "Janne", "Teuvo", "Sami", "Jari", "Artturi", "Jesse", "Kasperi", "Roope", "Aatu", "Joel", "Rasmus", "Niko", "Santtu", "Veeti", "Joona", "Topias", "Otto", "Onni", "Väinö", "Leevi", "Aku", "Niilo", "Eemil", "Aleksis", "Nooa", "Riku", "Tuukka", "Kasper", "Elmeri"],
    "Russia": ["Andrei", "Sergei", "Vladimir", "Alexander", "Ivan", "Dmitri", "Mikhail", "Nikita", "Evgeni", "Pavel", "Maxim", "Yuri", "Igor", "Kirill", "Fyodor", "Ilya", "Artem", "Slava", "Vasili", "Denis", "Alexei", "Viktor", "Oleg", "Roman", "Anatoli", "Boris", "Leonid", "Valentin", "Grigory", "Stanislav", "Ruslan", "Vladislav", "Anton", "Konstantin", "Georgi", "Nikolai", "Pyotr", "Stepan", "Timur", "Yegor", "Zakhar", "Matvei"],
    "Czech": ["Jakub", "Jan", "Tomáš", "David", "Pavel", "Martin", "Filip", "Petr", "Jiří", "Dominik", "Radek", "Marek", "Michal", "Lukáš", "Josef", "Roman", "Ondrej", "Daniel", "Karel", "Miroslav", "Vojtěch", "Adam", "Matěj", "Štěpán", "Václav", "Patrik", "Aleš", "Milan", "Zdeněk", "Libor", "Stanislav", "Vlastimil", "Jaroslav", "Miloslav", "Vladimír", "František", "Rudolf", "Bohumil", "Ladislav", "Oldřich", "Antonín", "Bedřich"],
    "Other": ["Juraj", "Marco", "Leon", "Darnell", "Nico", "Moritz", "Nino", "Timo", "Kevin", "Rafael", "Dominik", "Christoph", "Manuel", "David", "Thomas", "Marco", "Anze", "Jonas", "Mats", "Leo", "Lars", "Sven", "Hans", "Franz", "Klaus", "Dieter", "Wolfgang", "Stefan", "Andreas", "Michael", "Christian", "Alexander", "Sebastian", "Tobias", "Florian", "Daniel", "Philipp", "Lukas", "Simon", "Paul", "Felix", "Maximilian"]
}

EXTENDED_LAST_NAMES = {
    "Canada": ["Smith", "Brown", "Wilson", "Campbell", "Thompson", "MacDonald", "Clark", "Johnston", "Wright", "Dubois", "Roy", "Dube", "Lavoie", "Gagnon", "Bouchard", "Leblanc", "Gauthier", "Poulin", "Morin", "Cote", "Anderson", "Johnson", "Williams", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Perez", "Sanchez", "Ramirez", "Torres", "Flores", "Rivera", "Gomez", "Diaz", "Reyes", "Cruz"],
    "USA": ["Johnson", "Miller", "Williams", "Jones", "Brown", "Davis", "Anderson", "Wilson", "Taylor", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Robinson", "Lewis", "Walker", "Young", "Allen", "King", "Scott", "Green", "Baker", "Adams", "Nelson", "Carter", "Mitchell", "Perez", "Roberts", "Turner", "Phillips", "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart", "Sanchez", "Morris", "Rogers", "Reed"],
    "Sweden": ["Andersson", "Karlsson", "Nilsson", "Eriksson", "Larsson", "Olsson", "Lindqvist", "Petersson", "Svensson", "Gustafsson", "Lundqvist", "Nyquist", "Hedman", "Ekman-Larsson", "Hörnqvist", "Bäckström", "Silfverberg", "Zetterberg", "Hjalmarsson", "Ekholm", "Johansson", "Persson", "Lindberg", "Lundberg", "Holmberg", "Blomqvist", "Sandberg", "Hedberg", "Carlsson", "Mattsson", "Hansson", "Bengtsson", "Johnsson", "Fransson", "Eliasson", "Danielsson", "Månsson", "Pettersson", "Samuelsson", "Lindström", "Engström", "Nordström"],
    "Finland": ["Koivu", "Laine", "Rantanen", "Ristolainen", "Lindell", "Barkov", "Granlund", "Haula", "Donskoi", "Armia", "Nieminen", "Lehkonen", "Heiskanen", "Lankinen", "Rinne", "Rask", "Saros", "Heinola", "Teravainen", "Kakko", "Virtanen", "Puljujarvi", "Kapanen", "Hintz", "Luostarinen", "Jokiharju", "Honka", "Kupari", "Tuulola", "Ylonen", "Raty", "Kotkaniemi", "Ruotsalainen", "Talvitie", "Hirvonen", "Kiviharju", "Nurmi", "Saarela", "Ojala", "Vanhala", "Kinnunen", "Hakala"],
    "Russia": ["Ovechkin", "Malkin", "Kuznetsov", "Tarasenko", "Kucherov", "Vasilevskiy", "Bobrovsky", "Panarin", "Svechnikov", "Zadorov", "Provorov", "Zaitsev", "Orlov", "Podkolzin", "Romanov", "Kaprizov", "Kravtsov", "Shesterkin", "Sorokin", "Askarov", "Volkov", "Soshnikov", "Grigorenko", "Nichushkin", "Barabanov", "Buchnevich", "Goldobin", "Kostin", "Samsonov", "Fedotov", "Chinakhov", "Denisenko", "Khusnutdinov", "Morozov", "Mukhamadullin", "Ponomarev", "Telnov", "Fomin", "Galimov", "Korshkov", "Kirsanov", "Shabanov"],
    "Czech": ["Nečas", "Palát", "Voráček", "Krejčí", "Kaše", "Zadina", "Hronek", "Chytil", "Jaškin", "Faksa", "Zacha", "Polák", "Gudas", "Radil", "Simon", "Nosek", "Frk", "Šustr", "Rutta", "Jeřábek", "Pastrnak", "Hertl", "Plekanec", "Hanzal", "Sobotka", "Frolik", "Michalek", "Cernak", "Kempny", "Vrana", "Dvorak", "Kase", "Spacek", "Zboril", "Hajek", "Kral", "Lauko", "Blumel", "Stransky", "Cermak", "Rousek", "Mysak"],
    "Other": ["Kopitar", "Josi", "Niederreiter", "Ehlers", "Meier", "Hischier", "Fiala", "Draisaitl", "Kahun", "Sturm", "Greiss", "Raffl", "Grabner", "Vanek", "Zuccarello", "Fasth", "Diaz", "Sbisa", "Streit", "Hansen", "Kurashev", "Stutzle", "Seider", "Peterka", "Reichel", "Bokk", "Grans", "Broberg", "Soderstrom", "Holtz", "Raymond", "Lundell", "Wallinder", "Cossa", "Niederbach", "Gunler", "Mastrosimone", "Mercer", "Stillman", "Foerster", "Bolduc", "Lambos"]
}

# Extended birthplace data for international depth
EXTENDED_BIRTHPLACES = {
    "Canada": [
        "Toronto, ON", "Montreal, QC", "Vancouver, BC", "Calgary, AB", "Edmonton, AB", 
        "Winnipeg, MB", "Ottawa, ON", "Halifax, NS", "Quebec City, QC", "Mississauga, ON",
        "London, ON", "Kelowna, BC", "Regina, SK", "Saskatoon, SK", "Thunder Bay, ON",
        "Hamilton, ON", "Kitchener, ON", "Victoria, BC", "Windsor, ON", "Oshawa, ON",
        "Barrie, ON", "Guelph, ON", "Kingston, ON", "Sudbury, ON", "Sault Ste. Marie, ON",
        "Prince George, BC", "Red Deer, AB", "Lethbridge, AB", "Medicine Hat, AB", "Grande Prairie, AB",
        "Brandon, MB", "Portage la Prairie, MB", "Fredericton, NB", "Saint John, NB", "Charlottetown, PE",
        "St. John's, NL", "Whitehorse, YT", "Yellowknife, NT", "Iqaluit, NU"
    ],
    "USA": [
        "Boston, MA", "Chicago, IL", "Minneapolis, MN", "Detroit, MI", "Buffalo, NY", 
        "St. Paul, MN", "New York, NY", "Grand Forks, ND", "Pittsburgh, PA", "Anchorage, AK",
        "Madison, WI", "Ann Arbor, MI", "St. Louis, MO", "Philadelphia, PA", "Las Vegas, NV",
        "Denver, CO", "Portland, OR", "Seattle, WA", "Los Angeles, CA", "San Jose, CA",
        "Phoenix, AZ", "Dallas, TX", "Houston, TX", "Atlanta, GA", "Miami, FL",
        "Tampa, FL", "Nashville, TN", "Columbus, OH", "Cleveland, OH", "Cincinnati, OH",
        "Indianapolis, IN", "Milwaukee, WI", "Kansas City, MO", "Omaha, NE", "Salt Lake City, UT",
        "Boise, ID", "Spokane, WA", "Billings, MT", "Fargo, ND", "Sioux Falls, SD"
    ],
    "Sweden": [
        "Stockholm", "Gothenburg", "Malmo", "Uppsala", "Linkoping", 
        "Vasteras", "Orebro", "Umea", "Lulea", "Karlstad",
        "Helsingborg", "Jonkoping", "Norrkoping", "Lund", "Vasteras",
        "Gavle", "Boras", "Eskilstuna", "Halmstad", "Kristianstad",
        "Trollhattan", "Uddevalla", "Skelleftea", "Karlskrona", "Falun",
        "Sandviken", "Borlange", "Kiruna", "Ostersund", "Visby"
    ],
    "Finland": [
        "Helsinki", "Tampere", "Turku", "Espoo", "Vantaa", 
        "Oulu", "Jyvaskyla", "Kuopio", "Lahti", "Pori",
        "Rovaniemi", "Vaasa", "Joensuu", "Lappeenranta", "Hameenlinna",
        "Rauma", "Savonlinna", "Seinajoki", "Mikkeli", "Kotka",
        "Kouvola", "Porvoo", "Riihimaki", "Tornio", "Kajaani",
        "Iisalmi", "Ylivieska", "Raahe", "Forssa", "Pietarsaari"
    ],
    "Russia": [
        "Moscow", "St. Petersburg", "Chelyabinsk", "Magnitogorsk", "Yaroslavl", 
        "Yekaterinburg", "Omsk", "Novosibirsk", "Kazan", "Ufa",
        "Volgograd", "Rostov-on-Don", "Krasnoyarsk", "Perm", "Voronezh",
        "Saratov", "Krasnodar", "Tolyatti", "Izhevsk", "Barnaul",
        "Vladivostok", "Irkutsk", "Khabarovsk", "Novokuznetsk", "Ryazan",
        "Tula", "Lipetsk", "Penza", "Astrakhan", "Naberezhnyye Chelny"
    ],
    "Czech": [
        "Prague", "Brno", "Ostrava", "Kladno", "Plzen", 
        "Liberec", "Olomouc", "Pardubice", "Zlin", "Karlovy Vary",
        "Hradec Kralove", "Ceske Budejovice", "Usti nad Labem", "Teplice", "Most",
        "Chomutov", "Jihlava", "Trebic", "Frydek-Mistek", "Karvina",
        "Prerov", "Havlickuv Brod", "Trinec", "Vsetin", "Litvinov"
    ],
    "Other": [
        "Bratislava, SVK", "Kosice, SVK", "Vienna, AUT", "Graz, AUT", "Bern, CHE", 
        "Zurich, CHE", "Basel, CHE", "Berlin, DEU", "Munich, DEU", "Cologne, DEU",
        "Hamburg, DEU", "Dresden, DEU", "Leipzig, DEU", "Ljubljana, SVN", "Maribor, SVN",
        "Oslo, NOR", "Bergen, NOR", "Trondheim, NOR", "Copenhagen, DNK", "Aarhus, DNK",
        "Odense, DNK", "Aalborg, DNK", "Riga, LVA", "Vilnius, LTU", "Tallinn, EST",
        "Minsk, BLR", "Kiev, UKR", "Lviv, UKR", "Zagreb, HRV", "Split, HRV"
    ]
}

# League structures for different database sizes - Updated with authentic real-world data
LEAGUE_STRUCTURES = {
    "Small": [
        {"name": "National Hockey League", "level": 1, "teams": 32, "country": "North America"},
        {"name": "American Hockey League", "level": 2, "teams": 30, "country": "North America"}
    ],
    "Medium": [
        {"name": "National Hockey League", "level": 1, "teams": 32, "country": "North America"},
        {"name": "American Hockey League", "level": 2, "teams": 30, "country": "North America"},
        {"name": "ECHL", "level": 3, "teams": 24, "country": "North America"},
        {"name": "Swedish Hockey League", "level": 1, "teams": 14, "country": "Sweden"},
        {"name": "Finnish Liiga", "level": 1, "teams": 16, "country": "Finland"}
    ],
    "Large": [
        {"name": "National Hockey League", "level": 1, "teams": 32, "country": "North America"},
        {"name": "American Hockey League", "level": 2, "teams": 30, "country": "North America"},
        {"name": "ECHL", "level": 3, "teams": 26, "country": "North America"},
        {"name": "SPHL", "level": 4, "teams": 12, "country": "North America"},
        {"name": "Swedish Hockey League", "level": 1, "teams": 14, "country": "Sweden"},
        {"name": "HockeyAllsvenskan", "level": 2, "teams": 14, "country": "Sweden"},
        {"name": "Finnish Liiga", "level": 1, "teams": 16, "country": "Finland"},
        {"name": "Mestis", "level": 2, "teams": 12, "country": "Finland"},
        {"name": "KHL", "level": 1, "teams": 23, "country": "Russia"},
        {"name": "VHL", "level": 2, "teams": 24, "country": "Russia"},
        {"name": "Czech Extraliga", "level": 1, "teams": 14, "country": "Czech"},
        {"name": "Swiss National League", "level": 1, "teams": 14, "country": "Other"}
    ],
    "Massive": [
        {"name": "National Hockey League", "level": 1, "teams": 32, "country": "North America"},
        {"name": "American Hockey League", "level": 2, "teams": 30, "country": "North America"},
        {"name": "ECHL", "level": 3, "teams": 26, "country": "North America"},
        {"name": "SPHL", "level": 4, "teams": 12, "country": "North America"},
        {"name": "FHL", "level": 5, "teams": 8, "country": "North America"},
        {"name": "LNAH", "level": 5, "teams": 6, "country": "North America"},
        {"name": "Swedish Hockey League", "level": 1, "teams": 14, "country": "Sweden"},
        {"name": "HockeyAllsvenskan", "level": 2, "teams": 14, "country": "Sweden"},
        {"name": "HockeyEttan", "level": 3, "teams": 48, "country": "Sweden"},
        {"name": "Finnish Liiga", "level": 1, "teams": 16, "country": "Finland"},
        {"name": "Mestis", "level": 2, "teams": 12, "country": "Finland"},
        {"name": "Suomi-sarja", "level": 3, "teams": 24, "country": "Finland"},
        {"name": "KHL", "level": 1, "teams": 23, "country": "Russia"},
        {"name": "VHL", "level": 2, "teams": 24, "country": "Russia"},
        {"name": "MHL", "level": 3, "teams": 32, "country": "Russia"},
        {"name": "Czech Extraliga", "level": 1, "teams": 14, "country": "Czech"},
        {"name": "Czech 1.Liga", "level": 2, "teams": 14, "country": "Czech"},
        {"name": "Swiss National League", "level": 1, "teams": 14, "country": "Other"},
        {"name": "Swiss League", "level": 2, "teams": 10, "country": "Other"},
        {"name": "DEL", "level": 1, "teams": 14, "country": "Other"},
        {"name": "DEL2", "level": 2, "teams": 14, "country": "Other"},
        {"name": "ICEHL", "level": 1, "teams": 13, "country": "Other"},
        {"name": "Slovak Extraliga", "level": 1, "teams": 12, "country": "Other"},
        {"name": "Norwegian Eliteserien", "level": 1, "teams": 10, "country": "Other"},
        {"name": "Danish Metal Ligaen", "level": 1, "teams": 9, "country": "Other"}
    ]
}

class DatabaseGenerator:
    """Enhanced database generator with multiple realism levels"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.generated_players = []
        self.generated_teams = []
        self.generated_leagues = []
        # Fantasy-draft starts are an even playing field: when True, the
        # day-one cap situations (payroll targets + compliance backstop)
        # are skipped so the draft pool is unshaped. Set by main.py from
        # the launcher's fantasy_draft option before generation.
        self.fantasy_draft_mode = False
        
    def generate_comprehensive_database(self, progress_callback=None) -> League:
        """Generate a complete hockey database based on configuration"""
        
        def update_progress(percentage, status, detail=""):
            if progress_callback:
                progress_callback(percentage, status, detail)
        
        update_progress(0, f"Initializing {self.config.name}...")
        print(f"Generating {self.config.name}...")
        print(f"Target: {self.config.total_players:,} players across {self.config.leagues_count} leagues")
        
        # Create main league container
        main_league = League("Global Hockey Database")
        
        # Clear auto-generated teams since we want to create our own
        main_league.teams.clear()
        
        update_progress(10, "Creating league structure...", "Building teams and leagues")
        
        # Generate league structure (custom list wins; else fall back to size presets)
        league_data = self.config.league_infos or LEAGUE_STRUCTURES[self.config.name.split()[0]]
        
        # Generate teams for each league and track NHL/AHL teams
        teams_created = 0
        total_leagues = len(league_data)
        nhl_teams = []
        ahl_teams = []
        
        for i, league_info in enumerate(league_data):
            update_progress(10 + (i / total_leagues) * 15, 
                          f"Creating {league_info['name']}...", 
                          f"League {i+1} of {total_leagues}")
            
            league_teams = self._generate_league_teams(league_info)
            
            # Track NHL and AHL teams for affiliation
            if league_info['name'] == "National Hockey League":
                nhl_teams = league_teams
            elif league_info['name'] == "American Hockey League":
                ahl_teams = league_teams
                
            for team in league_teams:
                main_league.teams.append(team)
                teams_created += 1
        
        # Set up NHL-AHL affiliations
        if nhl_teams and ahl_teams:
            self._assign_ahl_affiliations(nhl_teams, ahl_teams)
        
        print(f"Created {teams_created} teams across {len(league_data)} leagues")
        update_progress(25, f"Created {teams_created} teams", f"Across {len(league_data)} leagues")
        
        # Calculate player distribution
        players_per_team = int(self.config.total_players * self.config.depth_factor / teams_created)
        total_needed = teams_created * players_per_team
        
        print(f"Generating approximately {players_per_team} players per team...")
        update_progress(30, "Generating team rosters...", f"Target: {players_per_team} players per team")
        
        # Generate players for each team
        players_created = 0
        for i, team in enumerate(main_league.teams):
            update_progress(30 + (i / teams_created) * 35, 
                          f"Generating roster for {team.team_name}...", 
                          f"Team {i+1} of {teams_created}")
            
            team_players = self._generate_team_roster(team, players_per_team)
            players_created += len(team_players)
        
        # Day-one cap situations: reshape NHL payrolls toward each club's
        # real 2026-27 posture (cap-strapped contenders tight, cap-flush
        # clubs with room) and guarantee no club starts over the cap.
        # Skipped for fantasy-draft starts -- even playing field, the
        # draft pool stays unshaped and cap compliance is not enforced
        # during the draft.
        if not self.fantasy_draft_mode:
            self._apply_day_one_cap_situations([
                t for t in main_league.teams
                if getattr(t, 'league_name', '') == "National Hockey League"])
        
        update_progress(65, "Generating free agent pool...", f"{players_created:,} team players created")
        
        # Generate free agents pool
        free_agents_count = max(150, int(self.config.total_players * 0.15))
        free_agents = self._generate_free_agents(free_agents_count)
        main_league.free_agents.extend(free_agents)
        players_created += len(free_agents)

        # D41 Phase 1: scout-speculation tiering. At generation there's no
        # user team yet, so tier with a neutral default eye; set_user_team
        # re-tiers through the user's actual head scout.
        try:
            from scout_tiering import tier_player as _tier_p
            for _fa in free_agents:
                try:
                    _tier_p(_fa, None)
                except Exception:
                    continue
        except Exception:
            pass
        
        # Generate free agent staff (staff pool expansion, Muck 2026-10-02:
        # dense + diverse so every position has real options).
        # Target ~450: deep enough for genuine choice at every position,
        # small enough that save/load stays fast (Staff objects are tiny).
        free_agent_staff_count = max(840, int(len(main_league.teams) * 28))
        free_agent_staff = self._generate_free_agent_staff(free_agent_staff_count)
        main_league.free_agent_staff.extend(free_agent_staff)

        # Generate overseas coaching talent (European clubs). Scouted and
        # approached like free agents -- no NHL contract to wait out.
        overseas_staff = self._generate_overseas_staff(40)
        main_league.overseas_staff.extend(overseas_staff)

        update_progress(80, "Generating prospect pools...", f"{len(free_agents)} free agents, {len(free_agent_staff)} staff created")
        
        # Generate prospects pool for upcoming drafts
        prospects = self._generate_prospects_pool(self.config.prospects_per_draft * 3)
        main_league.draft_prospects.extend(prospects)
        players_created += len(prospects)
        
        update_progress(95, "Finalizing database...", f"{len(prospects)} prospects created")
        
        # Generate staff for teams
        self._generate_team_staff(main_league.teams)

        # Jersey numbers: seed every club's real retired numbers (plus
        # league-wide 99), then deal numbers in seniority order so
        # established players land their favorites.
        try:
            import immortality as _im
            _yr = int(getattr(main_league, "season_year", 2026) or 2026)
            for _t in main_league.teams:
                try:
                    _im.seed_retired_numbers(_t)
                    _im.initial_number_assignment(_t, _yr)
                except Exception:
                    continue
        except Exception:
            pass

        # Link family members across the league (rare shared surnames)
        # and seed their relationships warm -- brothers start close.
        self._link_family_members(main_league)
        
        # Generate league schedule if needed
        if hasattr(main_league, 'generate_schedule'):
            main_league.generate_schedule()
        
        update_progress(100, "Database generation complete!", f"Total: {players_created:,} players")
        
        print(f"Database generation complete!")
        print(f"Total players generated: {players_created:,}")
        print(f"Teams: {teams_created}")
        print(f"Free agents: {len(free_agents)}")
        print(f"Prospects: {len(prospects)}")

        # P-5 is enforced at creation time by name_safety (star-surname
        # filter in the name generators) -- see the note in
        # main.setup_new_game for why there is no post-hoc scrub.

        return main_league
    
    # Two roster salary-share curves for a 23-man NHL roster, largest to
    # smallest, blended per club by payroll target (see
    # _generate_cap_targeted_roster):
    # - _HEAVY_SHARES: star-heavy top end. Capped-out contenders carry
    #   this shape -- they are capped out BECAUSE they pay $12M+ talent.
    # - _FLAT_SHARES: flatter distribution. Cap-flush clubs get this --
    #   a team with $18M in space does not have a McDavid; its best
    #   player is a very good ~$8M piece, and the money spreads into
    #   depth. Both normalized to sum to 1.0 at use time.
    _HEAVY_SHARES = (
        0.125, 0.098, 0.088, 0.080, 0.072, 0.066, 0.060, 0.055,
        0.050, 0.046, 0.042, 0.038, 0.035, 0.032, 0.030, 0.028,
        0.025, 0.022, 0.020, 0.018, 0.015, 0.012, 0.006,
    )
    _FLAT_SHARES = (
        0.095, 0.085, 0.078, 0.072, 0.066, 0.061, 0.056, 0.052,
        0.048, 0.044, 0.041, 0.038, 0.035, 0.032, 0.030, 0.028,
        0.026, 0.024, 0.022, 0.020, 0.017, 0.014, 0.010,
    )
    # Payroll-target range the blend interpolates across: ~$82M (fully
    # flat -- the most cap-flush clubs) to ~$103.5M (fully star-heavy --
    # the capped-out contenders).
    _BLEND_LO = 82_000_000
    _BLEND_HI = 103_500_000

    _qm_salary_calib = None  # lazily calibrated [(median_salary, qm)]

    def _calibrate_quality(self):
        """Measure the median salary each quality_modifier produces.

        Maps quality -> pay so roster generation can aim players at salary
        targets. Calibrated once per generator with veteran-age players
        (no ELC distortion); piecewise-linear inversion at use time.
        """
        pts = []
        for qm in (0.55, 0.75, 0.95, 1.15, 1.35, 1.55):
            sals = []
            for _ in range(24):
                p = self._create_enhanced_player(random.randint(26, 31),
                                                 PlayerPosition.CENTER, qm)
                sals.append(int(getattr(getattr(p, "contract", None),
                                        "salary", 0) or 0))
            sals.sort()
            if sals:
                pts.append((sals[len(sals) // 2], qm))
        pts.sort()
        return pts

    def _quality_for_salary(self, salary: float) -> float:
        """quality_modifier expected to produce ~salary, by calibration."""
        if self._qm_salary_calib is None:
            self._qm_salary_calib = self._calibrate_quality()
        pts = self._qm_salary_calib or []
        if not pts:
            return 1.0
        if salary <= pts[0][0]:
            return 0.55
        if salary >= pts[-1][0]:
            return 1.70
        for (s0, q0), (s1, q1) in zip(pts, pts[1:]):
            if s0 <= salary <= s1:
                f = (salary - s0) / (s1 - s0) if s1 > s0 else 0.0
                return q0 + f * (q1 - q0)
        return 1.0

    def _generate_cap_targeted_roster(self, team: Team):
        """Generate a 23-man NHL roster tracking the club's payroll target.

        Day-one cap situations: the target is cap - seeded dead cap -
        the club's real 2026-27 projected room (real_cap_data). Each pick
        aims at its share of the remaining budget, so the roster shape
        mimics a real club (stars up top, cheap depth at the bottom) and
        the total lands near the target. Star concentration follows the
        money: high-payroll clubs blend toward the star-heavy curve
        (that's why they're capped out), low-payroll clubs toward the
        flat curve (cap space means no $13M superstar on the roster).
        Contracts come from the same 2026-market gates as everywhere
        else; the loop self-corrects when the dice come in hot or cold.
        Returns None if no target could be computed (caller falls back
        to the classic path), or when the game starts with a fantasy
        draft (even playing field -- the draft pool stays unshaped).
        """
        if getattr(self, "fantasy_draft_mode", False):
            return None
        try:
            import real_cap_data as _rcd
            from salary_cap_system import DEFAULT_CAP as _CAP
            key = _rcd._team_key(team)
            target = (_CAP - _rcd.total_dead_cap(key)
                      - _rcd.target_cap_room(key))
        except Exception:
            return None

        positions = ([PlayerPosition.CENTER, PlayerPosition.RIGHT_WING,
                      PlayerPosition.LEFT_WING, PlayerPosition.LEFT_DEFENSE,
                      PlayerPosition.RIGHT_DEFENSE, PlayerPosition.GOALIE] * 4)[:23]
        # Blend flat <-> star-heavy by payroll target.
        _t = (target - self._BLEND_LO) / (self._BLEND_HI - self._BLEND_LO)
        _t = max(0.0, min(1.0, _t))
        shares = [f + _t * (h - f) for f, h in
                  zip(self._FLAT_SHARES, self._HEAVY_SHARES)][:len(positions)]
        total_share = sum(shares) or 1.0
        shares = [s / total_share for s in shares]

        players = []
        committed = 0
        for i, pos in enumerate(positions):
            share_left = sum(shares[i:])
            budget_left = target - committed
            if share_left > 0:
                target_sal = shares[i] / share_left * budget_left
            else:
                target_sal = budget_left
            target_sal = max(775_000, min(21_000_000, target_sal))
            # Tier-consistent dice: the shared contract gates are tiered
            # on overall (95+ superstar money, 90+ premium), so one lucky
            # 95 on an $8M slot would sign for $16M+ and break the club's
            # shape -- a cap-flush team must never roll a McDavid. Age
            # follows the money (stars are veterans, depth is young, and
            # cheap slots can land ELC talent like real clubs); the aim
            # steers toward the slot and tier-crossers are re-rolled.
            # A slot paying less than premium money must not roll premium
            # talent (and premium slots must not roll a superstar): the
            # tiered gates would pay them far above the slot and hand a
            # cap-flush club a McDavid. ELC-age slots are exempt -- the
            # entry-level scale caps their pay whatever they roll.
            if target_sal >= 5_000_000:
                age_lo, age_hi = 26, 33
            elif target_sal >= 2_000_000:
                age_lo, age_hi = 23, 30
            else:
                age_lo, age_hi = 18, 24
            if target_sal < 9_000_000:
                tier_cap = 89
            elif target_sal < 12_000_000:
                tier_cap = 94
            else:
                tier_cap = 100
            # Franchise premium: a capped-out club's #1 pick is where the
            # $15M+ deals live in real life (Makar $20.4M, Celebrini
            # $18.8M). The fatter slot plus an open superstar tier lets
            # the dice land a true franchise player; the loop's
            # self-correction keeps the payroll on target either way.
            if i == 0 and _t >= 0.85:
                target_sal *= 1.15
                tier_cap = 100
            best, best_miss = None, None
            qm = self._quality_for_salary(target_sal)
            for attempt in range(12):
                age = random.randint(age_lo, age_hi)
                q = max(0.50, min(1.70, qm * random.uniform(0.96, 1.04)))
                cand = self._create_enhanced_player(age, pos, q)
                if age > 22 and cand.overall_rating() > tier_cap:
                    # Tier-crossing: this quality runs too hot for the
                    # slot -- cool the aim and re-roll, never sign.
                    qm *= 0.94
                    continue
                sal = int(getattr(getattr(cand, "contract", None),
                                  "salary", 0) or 0)
                miss = abs(sal - target_sal)
                if best is None or miss < best_miss:
                    best, best_miss = cand, miss
                if miss <= target_sal * 0.25:
                    break
                # Steer the aim toward the slot: hot rolls cool it, cold
                # rolls warm it. (ELC-age salaries don't move with
                # quality, so only steer once the entry-level scale no
                # longer caps the pay.)
                if age > 22:
                    if sal > target_sal * 1.10:
                        qm *= 0.95
                    elif sal < target_sal * 0.90:
                        qm *= 1.05
            if best is None:
                best = self._create_enhanced_player(
                    random.randint(age_lo, age_hi), pos,
                    max(0.50, min(1.70, qm * 0.90)))
            players.append(best)
            committed += int(getattr(getattr(best, "contract", None),
                                     "salary", 0) or 0)
        return players

    def _apply_day_one_cap_situations(self, nhl_teams: List[Team]) -> None:
        """Reshape day-one NHL payrolls toward real 2026-27 cap situations.

        Each club gets a payroll target (cap - seeded dead cap - real
        projected room, via real_cap_data), and each roster is generated
        closed-loop against its own target with a star-concentration
        shape that follows the money: capped-out contenders (Vegas,
        Toronto, Edmonton...) are top-heavy because they pay $12M+
        talent, while cap-flush clubs (Detroit, Seattle, Vancouver...)
        are flat -- no McDavid on a team with $18M in space -- and hold
        room to weaponize. Deliberately no cross-team swaps: moving an
        expensive star to an under-target club would hand flat teams
        superstars and destroy the shape. A proportional scale-down
        backstops any club still over the cap afterwards: no team may
        start in violation.
        """
        try:
            import real_cap_data as _rcd
            from salary_cap_system import DEFAULT_CAP as _CAP
        except Exception:
            return
        if not nhl_teams:
            return

        def _sal(p) -> int:
            return int(getattr(getattr(p, "contract", None), "salary", 0) or 0)

        def _payroll(team) -> int:
            return sum(_sal(p) for p in (getattr(team, "roster", None) or []))

        # Hard compliance safety net (same rule as the classic path).
        # Measured on the TRUE cap charge -- active roster + minor-league
        # burial + real seeded dead cap -- so a club can't slip over via
        # buried one-way money in the minors.
        try:
            from salary_cap_system import roster_cap_charge as _rcc
        except Exception:
            _rcc = None
        for team in nhl_teams:
            key = _rcd._team_key(team)
            dead = _rcd.total_dead_cap(key)
            cap_target = _CAP - 500_000  # max allowed total charge
            roster = list(getattr(team, "roster", None) or [])
            for _ in range(10):
                pay = ((_rcc(team) if _rcc else _payroll(team)) + dead)
                if pay <= cap_target or cap_target <= 0:
                    break
                scale = (cap_target - dead) / max(1, pay - dead)
                for p in roster:
                    c = getattr(p, "contract", None)
                    if c is not None:
                        c.salary = max(775_000,
                                       int(c.salary * scale // 25000 * 25000))

    def _link_family_members(self, league):
        """Link family members across the league.

        Players sharing a RARE surname (2-4 league-wide, so no 'Smith
        brothers' false positives from common names) are family in the
        game world -- the Staals/Hughes treatment. Links are mutual and
        their relationships start warm; the monthly relationship engine
        takes it from there.
        """
        try:
            pool = []
            for team in getattr(league, 'teams', []) or []:
                pool.extend(getattr(team, 'roster', []) or [])
            pool.extend(getattr(league, 'free_agents', []) or [])
            # Draft prospects too -- brothers in the same draft class
            # (the Hughes/Staal treatment) are exactly this flavor.
            pool.extend(getattr(league, 'draft_prospects', []) or [])

            by_surname = {}
            for p in pool:
                sn = (getattr(p, 'last_name', '') or '').strip()
                if sn:
                    by_surname.setdefault(sn, []).append(p)

            for surname, members in by_surname.items():
                if not 2 <= len(members) <= 4:
                    continue
                if any(len(getattr(m, 'family_ids', None) or []) >= 2 for m in members):
                    continue  # already spoken for -- keep families small
                ids = [m.id for m in members]
                for m in members:
                    fam = getattr(m, 'family_ids', None)
                    if fam is None:
                        m.family_ids = fam = []
                    for oid in ids:
                        if oid != m.id and oid not in fam:
                            fam.append(oid)
                    # Brothers start close.
                    rels = getattr(m, 'relationships', None)
                    if rels is None:
                        m.relationships = rels = {}
                    for oid in ids:
                        if oid != m.id:
                            rels[oid] = max(rels.get(oid, 0), 80)
        except Exception:
            pass  # family linking is flavor -- never break generation

    def _generate_team_staff(self, teams):
        """Generate coaching staff and management for all teams."""
        from game_classes import Staff, StaffRole, default_staff_budget

        staff_positions = list(TEAM_STAFF_TEMPLATE)

        first_names = [
            "Adam", "Alex", "Andrew", "Anthony", "Brian", "Bruce", "Carl", "Chris", "Craig", "Dan",
            "Dave", "David", "Doug", "Eric", "Frank", "Gary", "Glen", "Greg", "Jack", "James",
            "Jeff", "Jim", "Joe", "John", "Ken", "Kevin", "Larry", "Mark", "Matt", "Mike",
            "Paul", "Peter", "Rick", "Rob", "Ron", "Scott", "Steve", "Tim", "Todd", "Tom"
        ]

        last_names = [
            "Anderson", "Brown", "Clark", "Davis", "Evans", "Garcia", "Harris", "Johnson", "Jones",
            "Lee", "Lewis", "Martin", "Miller", "Moore", "Robinson", "Rodriguez", "Smith", "Taylor",
            "Thomas", "Thompson", "White", "Williams", "Wilson", "Young", "Adams", "Baker", "Campbell",
            "Carter", "Collins", "Cooper", "Edwards", "Green", "Hall", "Hill", "Jackson", "King",
            "Lopez", "Mitchell", "Nelson", "Parker", "Perez", "Phillips", "Roberts", "Turner", "Walker"
        ]

        # Minor-league staff: every club's AHL affiliate gets a head coach,
        # two assistants, and a GM running the farm. They count against the
        # staff budget and can only be approached by other clubs in the
        # offseason (real-world rule).
        # AHL salaries are tiered by role (farm pay runs well below NHL
        # equivalents) so the full org fits the small-market staff budget.
        ahl_positions = [
            (StaffRole.HEAD_COACH, 1, 200_000),
            (StaffRole.ASSISTANT_COACH, 2, 120_000),
            (StaffRole.GENERAL_MANAGER, 1, 150_000),
        ]

        for team in teams:
            debug_print(f"Generating staff for {team.team_name}...")
            # League-wide staff budget, tiered by market size.
            team.staff_budget = default_staff_budget(team.team_name)

            for role, count, salary in staff_positions:
                for _ in range(count):
                    first_name = random.choice(first_names)
                    last_name = random.choice(last_names)

                    # Create staff member using the dataclass constructor.
                    # Tiered salary keeps the full staff inside the
                    # small-market budget with room to hire.
                    staff_member = Staff(
                        first_name=first_name,
                        last_name=last_name,
                        role=role,
                        age=random.randint(35, 65),
                        experience=random.randint(1, 20),
                        assignment="nhl",
                        salary=salary + random.randint(-20_000, 20_000),
                    )

                    # Add to team staff
                    team.staff.append(staff_member)

            for role, count, salary in ahl_positions:
                for _ in range(count):
                    staff_member = Staff(
                        first_name=random.choice(first_names),
                        last_name=random.choice(last_names),
                        role=role,
                        age=random.randint(30, 60),
                        experience=random.randint(1, 15),
                        assignment="ahl",
                        salary=salary + random.randint(-15_000, 15_000),
                    )
                    team.staff.append(staff_member)
    
    def _generate_free_agent_staff(self, count):
        """Generate unemployed staff members available for hiring.

        Staff pool expansion (Muck 2026-10-02): dense + diverse. Every
        hireable role gets real depth so replacing a coach/GM feels like
        a philosophical choice, not a warm body swap.

        Philosophy archetypes drive coherent attribute profiles:
        - Coaches: defensive / offensive / developmental / disciplinarian /
          player_coach / balanced
        - GMs: trader / draft_builder / cap_wizard / win_now / patient / balanced
        Ratings spread across tiers (elite 85-95 / solid 65-84 / project 40-64)
        and ages (young innovators / prime / veteran winners). Never raises.
        """
        from game_classes import Staff, StaffRole

        free_agent_staff = []
        available_roles = list(HIREABLE_STAFF_ROLES)

        first_names = [
            "Adam", "Alex", "Andrew", "Anthony", "Brian", "Bruce", "Carl", "Chris", "Craig", "Dan",
            "Dave", "David", "Doug", "Eric", "Frank", "Gary", "Glen", "Greg", "Jack", "James",
            "Jeff", "Jim", "Joe", "John", "Ken", "Kevin", "Larry", "Mark", "Matt", "Mike",
            "Paul", "Peter", "Rick", "Rob", "Ron", "Scott", "Steve", "Tim", "Todd", "Tom",
            "Barry", "Dale", "Dean", "Don", "Gerard", "Guy", "Jacques", "Joel", "Lindy", "Marc",
            "Michel", "Pascal", "Patrick", "Randy", "Roger", "Stan", "Terry", "Claude", "Alain",
        ]
        last_names = [
            "Anderson", "Brown", "Clark", "Davis", "Evans", "Garcia", "Harris", "Johnson", "Jones",
            "Lee", "Lewis", "Martin", "Miller", "Moore", "Robinson", "Rodriguez", "Smith", "Taylor",
            "Thomas", "Thompson", "White", "Williams", "Wilson", "Young", "Adams", "Baker", "Campbell",
            "Carter", "Collins", "Cooper", "Edwards", "Green", "Hall", "Hill", "Jackson", "King",
            "Lopez", "Mitchell", "Nelson", "Parker", "Perez", "Phillips", "Roberts", "Turner", "Walker",
            "Boudreau", "Carlyle", "Desjardins", "Gallant", "Hakstol", "Hitchcock", "Julien", "Keenan",
            "Laviolette", "MacLean", "Maurice", "McLellan", "Nelson", "Quenneville", "Roy", "Sutter",
            "Therrien", "Tippett", "Tortorella", "Vigneault", "Bowness", "Brunette", "Cassidy",
        ]

        # Coaching philosophy archetypes: attribute emphases for coherence.
        # Each maps philosophy -> {attr: bonus} applied on top of the tier base.
        COACH_ARCHETYPES = {
            "defensive": {"defensive_coaching": 12, "tactical_knowledge": 8,
                          "level_of_discipline": 8, "attacking_coaching": -6},
            "offensive": {"attacking_coaching": 12, "coaching_forwards": 8,
                          "game_preparation": 6, "defensive_coaching": -6},
            "developmental": {"working_with_youngsters": 14, "player_development": 12,
                              "mental_coaching": 8, "level_of_discipline": -4},
            "disciplinarian": {"level_of_discipline": 14, "discipline": 12,
                               "leadership": 8, "man_management": -8},
            "player_coach": {"man_management": 14, "motivating": 12,
                             "media_handling": 8, "level_of_discipline": -8},
            "balanced": {},
        }
        GM_ARCHETYPES = {
            "trader": {"adaptability": 10, "media_handling": 8, "determination": 6},
            "draft_builder": {"judging_player_potential": 14, "judging_player_ability": 8,
                              "working_with_youngsters": 8},
            "cap_wizard": {"tactical_knowledge": 10, "determination": 8, "adaptability": 6},
            "win_now": {"motivating": 10, "leadership": 8, "media_handling": 8},
            "patient": {"judging_player_potential": 10, "man_management": 8,
                        "determination": 8},
            "balanced": {},
        }

        def _tier_base():
            # Ratings spread: 15% elite, 55% solid, 30% project.
            r = random.random()
            if r < 0.15:
                return random.randint(85, 95)  # elite: proven winners
            elif r < 0.70:
                return random.randint(65, 84)  # solid: NHL-calibre
            return random.randint(40, 64)  # project: upside or retread

        def _make(role, philosophy=""):
            base = _tier_base()
            # Age/experience cohere with tier: elites skew veteran, projects skew young.
            if base >= 85:
                age = random.randint(48, 70)
                exp = random.randint(15, 30)
            elif base >= 65:
                age = random.randint(38, 60)
                exp = random.randint(8, 22)
            else:
                age = random.randint(30, 48)
                exp = random.randint(3, 12)

            def _attr(bonus=0):
                return max(1, min(99, int(random.gauss(base + bonus, 6))))

            kwargs = dict(
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                role=role,
                age=age,
                experience=exp,
            )
            # Apply philosophy archetype bonuses coherently.
            arch = {}
            if role in (StaffRole.HEAD_COACH, StaffRole.ASSOCIATE_COACH,
                        StaffRole.ASSISTANT_COACH, StaffRole.GOALIE_COACH,
                        StaffRole.POWER_PLAY_COACH, StaffRole.PENALTY_KILL_COACH):
                if not philosophy:
                    philosophy = random.choice(list(COACH_ARCHETYPES))
                arch = COACH_ARCHETYPES.get(philosophy, {})
                kwargs["coaching_philosophy"] = philosophy
            elif role == StaffRole.GENERAL_MANAGER:
                if not philosophy:
                    philosophy = random.choice(list(GM_ARCHETYPES))
                arch = GM_ARCHETYPES.get(philosophy, {})
                kwargs["gm_style"] = philosophy

            s = Staff(**kwargs)
            # Nudge key attributes toward the archetype.
            for attr, bonus in arch.items():
                try:
                    cur = getattr(s, attr, base)
                    setattr(s, attr, max(1, min(99, int(cur + bonus))))
                except Exception:
                    pass
            # Reputation tracks tier.
            try:
                s.reputation = max(10, min(95, int(random.gauss(base, 8))))
            except Exception:
                pass
            return s

        from game_classes import StaffRole as _SR
        # Per-role depth targets: key positions get real benches.
        depth_targets = {
            _SR.HEAD_COACH: 28,
            _SR.GENERAL_MANAGER: 24,
            _SR.ASSISTANT_COACH: 24,
            _SR.ASSOCIATE_COACH: 18,
            _SR.HEAD_SCOUT: 22,
            _SR.AMATEUR_SCOUT: 26,
            _SR.PROFESSIONAL_SCOUT: 22,
            _SR.EUROPEAN_SCOUT: 16,
            _SR.GOALIE_COACH: 18,
            _SR.POWER_PLAY_COACH: 14,
            _SR.PENALTY_KILL_COACH: 14,
            _SR.ANALYTICS_DIRECTOR: 14,
            _SR.ADVANCE_SCOUT: 12,
            _SR.SKILLS_COACH: 14,
            _SR.VIDEO_COACH: 12,
        }
        for role in available_roles:
            for _ in range(depth_targets.get(role, 8)):
                try:
                    free_agent_staff.append(_make(role))
                except Exception:
                    continue

        # Fill to the cap, weighted toward churn roles.
        weighted = (
            [_SR.HEAD_COACH] * 4 + [_SR.ASSISTANT_COACH] * 4
            + [_SR.ASSOCIATE_COACH] * 3 + [_SR.GOALIE_COACH] * 3
            + [_SR.PROFESSIONAL_SCOUT] * 3 + [_SR.AMATEUR_SCOUT] * 3
            + [_SR.HEAD_SCOUT] * 2 + [_SR.SKILLS_COACH] * 2
            + [_SR.ANALYTICS_DIRECTOR] * 2 + [_SR.GENERAL_MANAGER] * 2
        )
        guard = 0
        while len(free_agent_staff) < count and guard < count * 2:
            guard += 1
            try:
                role = random.choice(weighted or available_roles)
                free_agent_staff.append(_make(role))
            except Exception:
                continue

        return free_agent_staff

    def _generate_overseas_staff(self, count):
        """Generate coaches employed by European clubs (SHL, Liiga, NL, DEL,
        Czech Extraliga). They can be scouted and approached at any time --
        there is no NHL contract to wait out."""
        from game_classes import Staff, StaffRole

        roles = [
            StaffRole.HEAD_COACH,
            StaffRole.ASSISTANT_COACH,
            StaffRole.GOALIE_COACH,
            StaffRole.SKILLS_COACH,
            StaffRole.POWER_PLAY_COACH,
            StaffRole.PENALTY_KILL_COACH,
        ]
        first_names = [
            # Swedish / Finnish
            "Mats", "Lars", "Johan", "Anders", "Henrik", "Niklas", "Petter",
            "Mikko", "Jussi", "Antti", "Juho", "Ville", "Tomi", "Kari",
            # Czech / Slovak / German / Swiss
            "Pavel", "Tomas", "Marek", "Lukas", "Jan", "Martin", "Josef",
            "Marco", "Luca", "Nico", "Stefan", "Ralph", "Uwe", "Dmitri",
            # Russian
            "Alexei", "Sergei", "Igor", "Viktor", "Oleg", "Andrei",
        ]
        last_names = [
            "Lindqvist", "Karlsson", "Johansson", "Nilsson", "Bergström",
            "Virtanen", "Korhonen", "Mäkinen", "Nieminen", "Laine",
            "Novak", "Svoboda", "Dvorak", "Horvat", "Weber", "Müller",
            "Fischer", "Sturm", "Kovalenko", "Fedorov", "Sokolov",
        ]
        clubs = [
            "Frölunda HC (SHL)", "Djurgårdens IF (SHL)", "Färjestad BK (SHL)",
            "Tappara (Liiga)", "Kärpät (Liiga)", "HIFK (Liiga)",
            "ZSC Lions (NL)", "SC Bern (NL)", "EHC Biel (NL)",
            "Eisbären Berlin (DEL)", "Adler Mannheim (DEL)",
            "Sparta Praha (Extraliga)", "HC Kometa Brno (Extraliga)",
            "SKA St. Petersburg (KHL)", "CSKA Moscow (KHL)",
        ]
        nationalities = ["Sweden", "Finland", "Czech Republic", "Russia",
                         "Germany", "Switzerland", "Slovakia"]

        overseas = []
        for _ in range(count):
            club = random.choice(clubs)
            staff_member = Staff(
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                role=random.choice(roles),
                age=random.randint(32, 62),
                nationality=random.choice(nationalities),
                experience=random.randint(4, 22),
                assignment="overseas",
                current_club=club,
            )
            overseas.append(staff_member)
        return overseas
    
    def _generate_league_teams(self, league_info: dict) -> List[Team]:
        """Generate teams for a specific league"""
        teams = []
        country = league_info["country"]
        league_name = league_info["name"]
        
        # Use real team names for NHL and AHL
        if league_name == "National Hockey League":
            team_names = NHL_TEAMS[:league_info["teams"]]
        elif league_name == "American Hockey League":
            team_names = AHL_TEAMS[:league_info["teams"]]
        else:
            # Generate generic teams for other leagues
            if country == "North America":
                cities = EXTENDED_BIRTHPLACES["Canada"][:15] + EXTENDED_BIRTHPLACES["USA"][:15]
            elif country == "Sweden":
                cities = EXTENDED_BIRTHPLACES["Sweden"]
            elif country == "Finland":
                cities = EXTENDED_BIRTHPLACES["Finland"]
            elif country == "Russia":
                cities = EXTENDED_BIRTHPLACES["Russia"]
            elif country == "Czech":
                cities = EXTENDED_BIRTHPLACES["Czech"]
            else:
                cities = EXTENDED_BIRTHPLACES["Other"]
            
            # Generate team names and cities
            team_suffixes = ["Rangers", "Tigers", "Eagles", "Lions", "Bears", "Wolves", "Hawks", "Storm", "Thunder", "Lightning", "Ice", "Fire", "Steel", "Knights", "Warriors"]
            
            team_names = []
            for i in range(league_info["teams"]):
                if i < len(cities):
                    city = cities[i].split(",")[0]  # Remove province/state
                else:
                    city = f"City {i+1}"
                    
                team_name = f"{city} {random.choice(team_suffixes)}"
                team_names.append(team_name)
        
        # Create Team objects
        for team_name in team_names:
            # Extract city from team name
            if " " in team_name:
                city = team_name.split()[0]
            else:
                city = team_name
            
            # Get division and conference for NHL teams
            if league_name == "National Hockey League" and team_name in NHL_TEAM_INFO:
                division = NHL_TEAM_INFO[team_name]["division"]
                conference = NHL_TEAM_INFO[team_name]["conference"]
            else:
                # Default values for non-NHL teams
                division = "Unknown"
                conference = "Unknown"
                
            team = Team(team_name=team_name, city=city, division=division, conference=conference)
            team.league_name = league_info["name"]
            team.league_level = league_info["level"]
            teams.append(team)
        
        return teams
    
    def _assign_ahl_affiliations(self, nhl_teams: List[Team], ahl_teams: List[Team]):
        """Assign AHL teams as affiliates to NHL teams"""
        # Create parent-affiliate pairs (1:1 mapping)
        for i, nhl_team in enumerate(nhl_teams):
            if i < len(ahl_teams):
                ahl_team = ahl_teams[i]
                nhl_team.affiliate_team = ahl_team
                ahl_team.parent_team = nhl_team
    
    def _generate_team_roster(self, team: Team, target_size: int) -> List[Player]:
        """Generate a complete roster for a team with 50-player limit"""
        players = []
        
        # Enforce 50-player limit for NHL teams
        max_players = 50 if hasattr(team, 'league_name') and team.league_name == "National Hockey League" else target_size
        actual_target = min(target_size, max_players)
        
        # Professional distribution based on team level
        if hasattr(team, 'league_level'):
            level = team.league_level
        else:
            level = 1
            
        # Adjust player quality based on league level
        quality_modifier = max(0.5, 1.1 - (level * 0.15))
        
        # For NHL teams, distribute between NHL roster (23) and AHL/prospects (27)
        if hasattr(team, 'league_name') and team.league_name == "National Hockey League":
            nhl_roster_size = 23
            ahl_prospects_size = actual_target - nhl_roster_size

            # Generate NHL roster first -- against this club's real 2026-27
            # payroll target so day-one cap situations mirror real life
            # (falls back to the classic path if no target is available).
            nhl_players = self._generate_cap_targeted_roster(team)
            if nhl_players is None:
                nhl_players = self._generate_players_by_position(nhl_roster_size, quality_modifier * 1.1, team)
            for player in nhl_players:
                team.add_player(player, "roster")
                players.append(player)
            
            # Generate AHL/prospects
            ahl_prospects = self._generate_players_by_position(ahl_prospects_size, quality_modifier * 0.8, team)
            from player_generator import PlayerGenerator as _PG
            _pg = _PG()
            for i, player in enumerate(ahl_prospects):
                # Split between AHL and prospects
                roster_type = "ahl" if i < ahl_prospects_size * 0.7 else "prospects"
                team.add_player(player, roster_type)
                players.append(player)
                if roster_type == "ahl":
                    # Minor-league deals (two-way), mirroring the classic
                    # population path: one-way NHL money in the minors
                    # would pile up unrealistic burial charges on day one.
                    c = getattr(player, "contract", None)
                    if c is not None:
                        (sal, yrs, tw, ahl_sal) = _pg.determine_contract_info(
                            player, "AHL_VETERAN")
                        c.salary = sal
                        c.years_remaining = yrs
                        c.two_way = tw
                        c.ahl_salary = ahl_sal
                        # Minor-leaguers don't carry NHL clauses.
                        c.no_trade_clause = False
                        c.no_movement_clause = False
                        c.modified_ntc_teams = 0
                        c.modified_ntc_approved = False
                        c.ntc_waiver_for = ""
        else:
            # Non-NHL teams get all players in main roster
            all_players = self._generate_players_by_position(actual_target, quality_modifier, team)
            for player in all_players:
                team.add_player(player, "roster")
                players.append(player)
        
        return players
    
    def _generate_players_by_position(self, target_size: int, quality_modifier: float, team: Team) -> List[Player]:
        """Generate players distributed by position"""
        players = []
        
        # Generate by position with realistic distribution
        positions_needed = {
            PlayerPosition.GOALIE: max(2, int(target_size * 0.08)),
            PlayerPosition.LEFT_DEFENSE: max(3, int(target_size * 0.18)),
            PlayerPosition.RIGHT_DEFENSE: max(3, int(target_size * 0.18)),
            # Four full forward lines need 4 of each: 12 forwards minimum.
            # (Was 5C/3LW/3RW = 11, leaving F4_RW empty.)
            PlayerPosition.CENTER: max(4, int(target_size * 0.25)),
            PlayerPosition.LEFT_WING: max(4, int(target_size * 0.15)),
            PlayerPosition.RIGHT_WING: max(4, int(target_size * 0.16))
        }
        
        for position, count in positions_needed.items():
            for _ in range(count):
                # Age distribution based on veteran percentage
                if random.random() < self.config.veteran_distribution:
                    age = random.randint(25, 38)  # Veterans
                else:
                    age = random.randint(18, 24)  # Young players
                
                player = self._create_enhanced_player(age, position, quality_modifier)
                players.append(player)
        
        return players
    
    def _generate_free_agents(self, count: int) -> List[Player]:
        """Generate free agent players"""
        free_agents = []
        
        for _ in range(count):
            # Free agents tend to be older or lower quality
            age = random.randint(22, 40)
            position = self._get_weighted_position()
            quality_modifier = random.uniform(0.6, 0.9)  # Generally lower quality
            
            player = self._create_enhanced_player(age, position, quality_modifier)
            free_agents.append(player)
        
        return free_agents
    
    def _generate_prospects_pool(self, count: int) -> List[Player]:
        """Generate prospects for future drafts"""
        prospects = []
        
        for _ in range(count):
            # Prospects are young with varying potential
            age = random.randint(16, 20)
            position = self._get_weighted_position()
            quality_modifier = random.uniform(0.4, 1.2)  # Wide range of potential
            
            player = self._create_enhanced_player(age, position, quality_modifier)
            prospects.append(player)
        
        return prospects
    
    def _create_enhanced_player(self, age: int, position: PlayerPosition, quality_modifier: float = 1.0) -> Player:
        """Create a player with enhanced attributes based on database configuration"""
        
        # Select nationality with international factor
        nationality = self._get_weighted_nationality()
        
        # Get appropriate names
        first_name = random.choice(EXTENDED_FIRST_NAMES.get(nationality, EXTENDED_FIRST_NAMES["Other"]))
        # P-5: star-surname filter (Caleb's name_safety) -- generated players
        # must not borrow a recognizable real player's surname.
        try:
            import name_safety as _ns
            last_name = _ns.pick_surname(
                EXTENDED_LAST_NAMES.get(nationality, EXTENDED_LAST_NAMES["Other"]))
        except Exception:
            last_name = random.choice(EXTENDED_LAST_NAMES.get(nationality, EXTENDED_LAST_NAMES["Other"]))
        birthplace = random.choice(EXTENDED_BIRTHPLACES.get(nationality, EXTENDED_BIRTHPLACES["Other"]))
        
        # Create base player
        player = Player(
            first_name=first_name,
            last_name=last_name,
            age=age,
            primary_position=position
        )
        
        # Set enhanced personal information
        player.birthplace = birthplace
        player.nationality = nationality
        
        # Generate realistic physical attributes
        if position == PlayerPosition.GOALIE:
            # Goalies are typically taller
            feet = random.choices([5, 6], weights=[20, 80])[0]
            inches = random.randint(8, 11) if feet == 5 else random.randint(0, 5)
            player.height = f"{feet}'{inches}\""
            player.weight = random.randint(180, 220)
        elif position in [PlayerPosition.DEFENSE, PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]:
            # Defensemen are typically bigger
            feet = random.choices([5, 6], weights=[30, 70])[0]
            inches = random.randint(10, 11) if feet == 5 else random.randint(0, 4)
            player.height = f"{feet}'{inches}\""
            player.weight = random.randint(180, 230)
        else:
            # Forwards have more variation
            feet = random.choices([5, 6], weights=[40, 60])[0]
            inches = random.randint(8, 11) if feet == 5 else random.randint(0, 3)
            player.height = f"{feet}'{inches}\""
            player.weight = random.randint(160, 210)
        
        # Shooting hand based on position and nationality
        if position == PlayerPosition.GOALIE:
            player.handedness = random.choices(["Left", "Right"], weights=[60, 40])[0]  # More left-catching goalies
        else:
            # Shooting hand varies by nationality
            if nationality in ["Finland", "Sweden", "Russia"]:
                player.handedness = random.choices(["Left", "Right"], weights=[60, 40])[0]
            else:
                player.handedness = random.choices(["Left", "Right"], weights=[30, 70])[0]
        
        # Birth date and draft information
        birth_year = 2024 - age
        player.birth_date = f"{birth_year}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        
        if age >= 19:  # Eligible for draft
            draft_age = random.randint(18, 20)
            player.draft_year = birth_year + draft_age
            if age <= 25:  # Recent draft picks
                player.draft_position = f"Round {random.randint(1, 7)}, Pick {random.randint(1, 31)}"
            else:  # Older players might be undrafted or late picks
                if random.random() < 0.3:
                    player.draft_position = "Undrafted"
                else:
                    player.draft_position = f"Round {random.randint(3, 7)}, Pick {random.randint(1, 31)}"
        else:
            player.draft_year = birth_year + 18
            player.draft_position = "Not yet eligible"
        
        # Career information
        if age >= 20:
            player.pro_debut = f"{random.randint(birth_year + 18, birth_year + 22)}-10-{random.randint(1, 31):02d}"
            player.teams_count = min(random.randint(1, max(1, age - 17)), 6)
            
            tenure_options = ["This season", "2 years", "3 years", "4+ years"]
            weights = [40, 30, 20, 10] if age < 30 else [20, 25, 25, 30]
            player.team_tenure = random.choices(tenure_options, weights=weights)[0]
        else:
            player.pro_debut = "N/A"
            player.teams_count = 1
            player.team_tenure = "This season"
        
        # Potential and peak rating
        if age <= 22:
            player.potential = random.randint(60, 100)
            player.peak_rating = min(100, player.potential + random.randint(-10, 10))
        elif age <= 28:
            current_overall = random.randint(40, 90)
            player.potential = current_overall + random.randint(-10, 15)
            player.peak_rating = current_overall
        else:
            current_overall = random.randint(30, 80)
            player.potential = current_overall
            player.peak_rating = current_overall + random.randint(0, 20)
        
        # Health and injury information
        player.is_injured = random.random() < 0.05  # 5% chance of current injury
        player.days_missed = random.randint(0, 15) if not player.is_injured else 0
        player.career_games_missed = random.randint(0, min(50, age * 3))
        
        injury_types = ["None", "Upper body", "Lower body", "Concussion", "Broken bone", "Muscle strain"]
        weights = [70, 10, 10, 3, 4, 3]
        player.last_injury = random.choices(injury_types, weights=weights)[0]
        if player.is_injured:
            # BUG-026: a seeded injury needs a real countdown + type --
            # is_injured=True with games_remaining_injured=0 used to strand
            # the player sidelined forever (recovery only healed positive
            # counters). _process_injury_recovery now also heals zero
            # counters, so old saves recover too.
            player.games_remaining_injured = random.randint(2, 18)
            _t = random.choices(injury_types[1:], weights=weights[1:])[0]
            player.injury_type = _t
            player.last_injury = _t
        
        # Performance statistics based on position and age
        if age >= 18:
            # Season stats should start at 0 for new season
            player.games_played = 0
            
            if position == PlayerPosition.GOALIE:
                player.wins = 0
                player.losses = 0
                player.save_percentage = 0.000
                player.goals_against_avg = 0.00
                player.shutouts = 0
            else:
                # Season stats should start at 0 for new season
                player.goals = 0
                player.assists = 0
                player.points = 0
                player.plus_minus = 0
                player.avg_toi = "0:00"
        
        # Generate enhanced attributes based on age and quality
        self._set_enhanced_attributes(player, age, quality_modifier)
        
        # Generate contract information for professional players
        if age >= 18:
            player.contract = self._generate_contract(player, age)

        # Career NHL games: age-plausible service time, not a dice roll.
        # Young players start near zero and accrue real games from here
        # (see _credit_nhl_games_played); veterans arrive with a believable
        # history behind them. Drives waiver exemption.
        try:
            if age <= 20:
                player.nhl_games_played = 0
            elif age <= 22:
                player.nhl_games_played = random.randint(
                    0, (age - 20) * 60)
            else:
                _seasons = age - 21
                _per = random.randint(40, 78)
                if random.random() < 0.25:
                    # Fringe / late-bloomer: less NHL time.
                    _per = random.randint(5, 30)
                player.nhl_games_played = min(1400, _seasons * _per)
        except Exception:
            pass

        return player
    
    def _set_enhanced_attributes(self, player: Player, age: int, quality_modifier: float):
        """Set realistic attributes based on age, position, and quality.

        Uses the native 100-point attribute scale (same as player_generator
        and the sim engine): NHL-quality players land roughly 56-92 before
        age adjustment.
        """

        # Base attribute ranges adjusted by quality (100-point scale)
        base_min = max(10, int(56 * quality_modifier))
        base_max = min(100, int(88 * quality_modifier))
        
        # Age-based adjustments
        if age < 20:
            # Young players: lower current, higher potential
            current_factor = 0.7
            potential_boost = 1.3
        elif age < 25:
            # Prime development years
            current_factor = 0.9
            potential_boost = 1.1
        elif age < 30:
            # Peak years
            current_factor = 1.0
            potential_boost = 1.0
        else:
            # Veteran years
            current_factor = 0.9
            potential_boost = 0.8
        
        # Set core attributes
        core_attributes = ['skating', 'shooting', 'passing', 'checking', 'faceoffs', 
                          'determination', 'teamwork', 'leadership', 'discipline', 'flair',
                          'offensive_awareness', 'defensive_awareness', 'deking', 'strength']
        
        for attr in core_attributes:
            base_value = random.randint(base_min, base_max)
            adjusted_value = int(base_value * current_factor)
            adjusted_value = max(1, min(100, adjusted_value))
            setattr(player, attr, adjusted_value)
        
        # Position-specific attributes
        if player.primary_position == PlayerPosition.GOALIE:
            goalie_attrs = ['goaltending', 'reflexes', 'positioning', 'rebound_control', 'puck_handling']
            for attr in goalie_attrs:
                base_value = random.randint(min(100, base_min + 8), min(100, base_max + 12))
                adjusted_value = int(base_value * current_factor)
                adjusted_value = max(1, min(100, adjusted_value))
                setattr(player, attr, adjusted_value)
        
        # Advanced attributes
        advanced_attrs = ['vision', 'puck_control', 'shooting_accuracy', 'puck_protection', 
                         'stamina', 'shot_blocking', 'injury_proneness']
        
        for attr in advanced_attrs:
            if attr == 'injury_proneness':
                # Lower is better for injury proneness (1-100 scale)
                value = random.randint(5, 50)
            else:
                base_value = random.randint(base_min, base_max)
                value = int(base_value * current_factor)
                value = max(1, min(100, value))
            setattr(player, attr, value)
        
        # Set playing tendencies
        player.shooting_tendency = random.randint(20, 80)
        player.hitting_tendency = random.randint(20, 80)

        # Positioning split (2026-09-28, per Muck): every skater gets
        # offensive_positioning (getting open, net-front spot wins, shot
        # quality) and defensive_positioning (gap control, box-outs, blocks,
        # takeaways) on the native 100-point scale, tilted by position --
        # forwards lean offensive, defensemen lean defensive. Goalies keep
        # the single `positioning` (crease). ~1.5% unicorns come out elite
        # at both ends (the Bergeron/Coffey mold).
        if player.primary_position != PlayerPosition.GOALIE:
            _is_dman = player.primary_position in (
                PlayerPosition.DEFENSE, PlayerPosition.LEFT_DEFENSE,
                PlayerPosition.RIGHT_DEFENSE)
            if _is_dman:
                _off_range = (max(1, base_min - 12), max(1, base_max - 4))
                _def_range = (base_min + 2, min(100, base_max + 8))
            else:
                _off_range = (base_min + 2, min(100, base_max + 8))
                _def_range = (max(1, base_min - 12), max(1, base_max - 4))
            _off, _dfn = mesh_system.roll_positioning_split(
                _off_range[0], _off_range[1], _def_range[0], _def_range[1])
            player.offensive_positioning = max(
                1, min(100, int(_off * current_factor)))
            player.defensive_positioning = max(
                1, min(100, int(_dfn * current_factor)))
        
        # Set potential grade
        if age < 23:
            potential_grades = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]
            weights = [0.5, 2, 5, 8, 12, 15, 20, 20, 12, 4, 1.5]
        else:
            # Older players have lower potential for growth
            potential_grades = ["B-", "C+", "C", "C-", "D", "F"]
            weights = [5, 15, 25, 30, 20, 5]
        
        player.potential_grade = random.choices(potential_grades, weights=weights)[0]
    
    def _generate_contract(self, player: Player, age: int) -> Contract:
        """Generate a realistic contract for a player.

        Delegates to PlayerGenerator.determine_contract_info -- the single
        source of truth for the 2026 summer market (same gates the classic
        population path uses: 95+ superstar / 90+ premium, ELCs for kids,
        two-way structure, above-market bidding wars). The old inline
        bands below were written for the 1-50 attribute scale; on the
        native 1-100 scale every skater cleared the top band and landed at
        $7-12M, putting all 32 clubs ~$150M+ over the cap on day one.
        """
        from player_generator import PlayerGenerator as _PG
        _gen = _PG()
        overall = player.overall_rating()
        if overall >= 49:
            tier = "NHL_ELITE"
        elif overall >= 44:
            tier = "NHL_STARTER"
        else:
            tier = "NHL_DEPTH"
        salary, years, two_way, ahl_salary = _gen.determine_contract_info(player, tier)

        contract = Contract(
            salary=salary,
            years_remaining=years,
            two_way=two_way,
            ahl_salary=ahl_salary,
        )
        # Trade protection: the same demand model the user negotiates
        # against (trade_engine.clause_demand_score) -- stars with leverage
        # get clauses, kids don't, no flat dice roll.
        try:
            import trade_engine as _te
            _demand = _te.clause_demand_score(player)
            if random.random() < _demand * 0.85:
                _te.apply_clause_to_contract(
                    contract,
                    "nmc" if overall >= 86 and random.random() < 0.35
                    else ("mntc" if random.random() < 0.55 else "ntc"),
                    random.choice([8, 10, 12, 15, 16, 20]),
                    player=player)
        except Exception:
            pass

        return contract
    
    def _get_weighted_nationality(self) -> str:
        """Get nationality with international factor applied"""
        
        # Adjust distribution based on international factor
        base_dist = {
            "Canada": 0.45,
            "USA": 0.25,
            "Sweden": 0.08,
            "Finland": 0.05,
            "Russia": 0.05,
            "Czech": 0.04,
            "Other": 0.08
        }
        
        # Increase international representation
        if self.config.international_factor > 1.0:
            # Reduce North American representation
            reduction = (self.config.international_factor - 1.0) * 0.5
            base_dist["Canada"] -= reduction * 0.6
            base_dist["USA"] -= reduction * 0.4
            
            # Increase international representation
            international_keys = ["Sweden", "Finland", "Russia", "Czech", "Other"]
            boost_per_country = reduction / len(international_keys)
            
            for key in international_keys:
                base_dist[key] += boost_per_country
        
        # Ensure values are positive and sum to 1
        total = sum(base_dist.values())
        base_dist = {k: max(0.01, v/total) for k, v in base_dist.items()}
        
        countries = list(base_dist.keys())
        weights = list(base_dist.values())
        
        return random.choices(countries, weights=weights)[0]
    
    def _get_weighted_position(self) -> PlayerPosition:
        """Get position with realistic distribution"""
        
        distribution = {
            PlayerPosition.CENTER: 0.25,
            PlayerPosition.LEFT_WING: 0.15,
            PlayerPosition.RIGHT_WING: 0.15,
            PlayerPosition.LEFT_DEFENSE: 0.15,
            PlayerPosition.RIGHT_DEFENSE: 0.15,
            PlayerPosition.GOALIE: 0.15
        }
        
        positions = list(distribution.keys())
        weights = list(distribution.values())
        
        return random.choices(positions, weights=weights)[0]

def get_database_options() -> Dict[str, DatabaseConfig]:
    """Return available database configuration options"""
    return DATABASE_CONFIGURATIONS


def backfill_team_staff(league):
    """Additive old-save backfill for the R5 staff redesign.

    Saves generated before the full 24-role TEAM_STAFF_TEMPLATE get every
    club topped up to the template counts and the free-agent staff pool
    topped up to the per-role minimums. Existing staff are never removed,
    modified, or duplicated; unique roles (GM, head coach) are never
    doubled. Never raises -- a failed backfill just leaves the save as it
    was.
    """
    try:
        from game_classes import Staff, default_staff_budget
    except Exception:
        return
    try:
        teams = list(getattr(league, "teams", None) or [])
        if not teams:
            return
        first_names = ["Adam", "Alex", "Andrew", "Brian", "Chris", "Dan",
                       "Dave", "Eric", "Frank", "Jack", "James", "Joe",
                       "John", "Kevin", "Mark", "Mike", "Paul", "Scott",
                       "Steve", "Tim", "Todd", "Tom"]
        last_names = ["Anderson", "Brown", "Clark", "Davis", "Harris",
                      "Johnson", "Jones", "Lewis", "Martin", "Miller",
                      "Moore", "Smith", "Taylor", "Thomas", "Thompson",
                      "White", "Williams", "Wilson", "Young"]

        def _make(role, salary):
            return Staff(
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                role=role,
                age=random.randint(35, 65),
                experience=random.randint(1, 20),
                salary=int(salary) + random.randint(-20_000, 20_000),
            )

        unique_roles = {StaffRole.GENERAL_MANAGER, StaffRole.HEAD_COACH}
        for team in teams:
            staff = getattr(team, "staff", None)
            if not isinstance(staff, list):
                try:
                    team.staff = staff = []
                except Exception:
                    continue
            if getattr(team, "staff_budget", None) is None:
                try:
                    team.staff_budget = default_staff_budget(
                        getattr(team, "team_name", ""))
                except Exception:
                    pass
            have = {}
            for s in staff:
                r = getattr(s, "role", None)
                have[r] = have.get(r, 0) + 1
            for role, count, salary in TEAM_STAFF_TEMPLATE:
                try:
                    missing = int(count) - int(have.get(role, 0))
                except Exception:
                    missing = 0
                if missing <= 0:
                    continue
                if role in unique_roles and have.get(role, 0) >= 1:
                    continue  # never double the GM / head coach
                for _ in range(missing):
                    try:
                        staff.append(_make(role, salary))
                    except Exception:
                        break
                    have[role] = have.get(role, 0) + 1

        # Free-agent pool: guarantee the per-role minimums for hireable
        # roles so old saves can hire into any position.
        try:
            pool = getattr(league, "free_agent_staff", None)
            if not isinstance(pool, list):
                pool = []
                league.free_agent_staff = pool
            pool_have = {}
            for s in pool:
                r = getattr(s, "role", None)
                pool_have[r] = pool_have.get(r, 0) + 1
            for role in HIREABLE_STAFF_ROLES:
                need = 6 - int(pool_have.get(role, 0))
                for _ in range(max(0, need)):
                    try:
                        pool.append(Staff(
                            first_name=random.choice(first_names),
                            last_name=random.choice(last_names),
                            role=role,
                            age=random.randint(30, 70),
                            experience=random.randint(5, 25),
                        ))
                    except Exception:
                        break
        except Exception:
            pass
    except Exception:
        pass

def generate_database(config_name: str) -> League:
    """Generate a database using the specified configuration"""
    
    if config_name not in DATABASE_CONFIGURATIONS:
        raise ValueError(f"Unknown database configuration: {config_name}")
    
    config = DATABASE_CONFIGURATIONS[config_name]
    generator = DatabaseGenerator(config)
    
    return generator.generate_comprehensive_database()


# Example usage and testing
if __name__ == "__main__":
    # Test small database generation
    print("Testing database generation...")
    
    config = DATABASE_CONFIGURATIONS["Small"]
    generator = DatabaseGenerator(config)
    
    # Test individual components
    print("\nTesting player creation...")
    test_player = generator._create_enhanced_player(25, PlayerPosition.CENTER, 1.0)
    print(f"Created: {test_player.full_name} ({test_player.nationality}) - {test_player.overall_rating()}")
    
    print("\nDatabase configurations available:")
    for name, config in DATABASE_CONFIGURATIONS.items():
        print(f"- {name}: {config.description}")
