# database_generator.py
# Comprehensive database generation system inspired by Eastside Hockey Manager
# Supports multiple database sizes for different levels of realism and detail

import random
import math
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Callable, Union
from game_classes import Player, Team, League, PlayerPosition, GameBalance, Contract, debug_print
from dataclasses import dataclass

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
        
        update_progress(65, "Generating free agent pool...", f"{players_created:,} team players created")
        
        # Generate free agents pool
        free_agents_count = max(150, int(self.config.total_players * 0.15))
        free_agents = self._generate_free_agents(free_agents_count)
        main_league.free_agents.extend(free_agents)
        players_created += len(free_agents)
        
        # Generate free agent staff
        free_agent_staff_count = max(100, int(len(main_league.teams) * 2))  # ~2 staff per team as free agents
        free_agent_staff = self._generate_free_agent_staff(free_agent_staff_count)
        main_league.free_agent_staff.extend(free_agent_staff)
        
        update_progress(80, "Generating prospect pools...", f"{len(free_agents)} free agents, {len(free_agent_staff)} staff created")
        
        # Generate prospects pool for upcoming drafts
        prospects = self._generate_prospects_pool(self.config.prospects_per_draft * 3)
        main_league.draft_prospects.extend(prospects)
        players_created += len(prospects)
        
        update_progress(95, "Finalizing database...", f"{len(prospects)} prospects created")
        
        # Generate staff for teams
        self._generate_team_staff(main_league.teams)
        
        # Generate league schedule if needed
        if hasattr(main_league, 'generate_schedule'):
            main_league.generate_schedule()
        
        update_progress(100, "Database generation complete!", f"Total: {players_created:,} players")
        
        print(f"Database generation complete!")
        print(f"Total players generated: {players_created:,}")
        print(f"Teams: {teams_created}")
        print(f"Free agents: {len(free_agents)}")
        print(f"Prospects: {len(prospects)}")
        
        return main_league
    
    def _generate_team_staff(self, teams):
        """Generate coaching staff and management for all teams."""
        from game_classes import Staff, StaffRole
        
        # Staff positions and their frequency
        staff_positions = [
            (StaffRole.HEAD_COACH, 1),  # Each team needs 1 head coach
            (StaffRole.ASSISTANT_COACH, 2),  # 2 assistant coaches  
            (StaffRole.GOALIE_COACH, 1),  # 1 goalie coach
            (StaffRole.GENERAL_MANAGER, 1),  # 1 GM
            (StaffRole.PROFESSIONAL_SCOUT, 3),  # 3 scouts
        ]
        
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
        
        for team in teams:
            debug_print(f"Generating staff for {team.team_name}...")
            
            for role, count in staff_positions:
                for _ in range(count):
                    first_name = random.choice(first_names)
                    last_name = random.choice(last_names)
                    
                    # Create staff member using the dataclass constructor
                    staff_member = Staff(
                        first_name=first_name,
                        last_name=last_name,
                        role=role,
                        age=random.randint(35, 65),
                        experience=random.randint(1, 20)
                    )
                    
                    # Add to team staff
                    team.staff.append(staff_member)
    
    def _generate_free_agent_staff(self, count):
        """Generate unemployed staff members available for hiring."""
        from game_classes import Staff, StaffRole
        
        free_agent_staff = []
        
        # Staff roles that could be available as free agents
        available_roles = [
            StaffRole.HEAD_COACH,
            StaffRole.ASSISTANT_COACH,
            StaffRole.ASSOCIATE_COACH,
            StaffRole.GOALIE_COACH,
            StaffRole.GENERAL_MANAGER,
            StaffRole.ASSISTANT_GENERAL_MANAGER,
            StaffRole.HEAD_SCOUT,
            StaffRole.PROFESSIONAL_SCOUT,
            StaffRole.AMATEUR_SCOUT,
            StaffRole.EUROPEAN_SCOUT,
            StaffRole.SKILLS_COACH,
            StaffRole.CONDITIONING_COACH
        ]
        
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
        
        for _ in range(count):
            role = random.choice(available_roles)
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            
            # Free agent staff tend to be experienced but currently unemployed
            # This could be due to recent firing, retirement from previous role, etc.
            staff_member = Staff(
                first_name=first_name,
                last_name=last_name,
                role=role,
                age=random.randint(30, 70),  # Wider age range for free agents
                experience=random.randint(5, 25)  # Generally experienced
            )
            
            free_agent_staff.append(staff_member)
        
        return free_agent_staff
    
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
            
            # Generate NHL roster first
            nhl_players = self._generate_players_by_position(nhl_roster_size, quality_modifier * 1.1, team)
            for player in nhl_players:
                team.add_player(player, "roster")
                players.append(player)
            
            # Generate AHL/prospects
            ahl_prospects = self._generate_players_by_position(ahl_prospects_size, quality_modifier * 0.8, team)
            for i, player in enumerate(ahl_prospects):
                # Split between AHL and prospects
                roster_type = "ahl" if i < ahl_prospects_size * 0.7 else "prospects"
                team.add_player(player, roster_type)
                players.append(player)
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
            PlayerPosition.CENTER: max(4, int(target_size * 0.25)),
            PlayerPosition.LEFT_WING: max(3, int(target_size * 0.15)),
            PlayerPosition.RIGHT_WING: max(3, int(target_size * 0.16))
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
            player.potential = random.randint(12, 20)
            player.peak_rating = min(20, player.potential + random.randint(-2, 2))
        elif age <= 28:
            current_overall = random.randint(8, 18)
            player.potential = current_overall + random.randint(-2, 3)
            player.peak_rating = current_overall
        else:
            current_overall = random.randint(6, 16)
            player.potential = current_overall
            player.peak_rating = current_overall + random.randint(0, 4)
        
        # Health and injury information
        player.is_injured = random.random() < 0.05  # 5% chance of current injury
        player.days_missed = random.randint(0, 15) if not player.is_injured else 0
        player.career_games_missed = random.randint(0, min(50, age * 3))
        
        injury_types = ["None", "Upper body", "Lower body", "Concussion", "Broken bone", "Muscle strain"]
        weights = [70, 10, 10, 3, 4, 3]
        player.last_injury = random.choices(injury_types, weights=weights)[0]
        
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
        
        return player
    
    def _set_enhanced_attributes(self, player: Player, age: int, quality_modifier: float):
        """Set realistic attributes based on age, position, and quality.

        Uses the canonical ~50-point attribute scale (same as player_generator
        and the sim engine): NHL-quality players land roughly 28-46 before
        age adjustment.
        """

        # Base attribute ranges adjusted by quality (50-point scale)
        base_min = max(5, int(28 * quality_modifier))
        base_max = min(50, int(44 * quality_modifier))
        
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
            adjusted_value = max(1, min(50, adjusted_value))
            setattr(player, attr, adjusted_value)
        
        # Position-specific attributes
        if player.primary_position == PlayerPosition.GOALIE:
            goalie_attrs = ['goaltending', 'reflexes', 'positioning', 'rebound_control', 'puck_handling']
            for attr in goalie_attrs:
                base_value = random.randint(min(50, base_min + 4), min(50, base_max + 6))
                adjusted_value = int(base_value * current_factor)
                adjusted_value = max(1, min(50, adjusted_value))
                setattr(player, attr, adjusted_value)
        
        # Advanced attributes
        advanced_attrs = ['vision', 'puck_control', 'shooting_accuracy', 'puck_protection', 
                         'stamina', 'shot_blocking', 'injury_proneness']
        
        for attr in advanced_attrs:
            if attr == 'injury_proneness':
                # Lower is better for injury proneness
                value = random.randint(1, 10)
            else:
                base_value = random.randint(base_min, base_max)
                value = int(base_value * current_factor)
                value = max(1, min(50, value))
            setattr(player, attr, value)
        
        # Set playing tendencies
        player.shooting_tendency = random.randint(20, 80)
        player.hitting_tendency = random.randint(20, 80)
        
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
        """Generate a realistic contract for a player"""
        
        # Contract length based on age and quality
        if age < 25:
            years = random.choice([1, 2, 3])  # Entry level or short term
        elif age < 30:
            years = random.choice([2, 3, 4, 5])  # Prime years
        else:
            years = random.choice([1, 2, 3])  # Veteran contracts
        
        # Salary based on overall rating and age
        overall = player.overall_rating()
        
        if overall >= 47:
            salary = random.randint(7000000, 12000000)  # Elite players
        elif overall >= 44:
            salary = random.randint(4000000, 8000000)   # Top players
        elif overall >= 40:
            salary = random.randint(2000000, 5000000)   # Good players
        elif overall >= 37:
            salary = random.randint(900000, 2500000)    # Role players
        else:
            salary = random.randint(750000, 1200000)    # Depth players
        
        # Age adjustments
        if age < 23:
            salary = min(salary, 3000000)  # Entry level cap considerations
        elif age > 35:
            salary = int(salary * 0.7)  # Veteran discounts
        
        contract = Contract(
            salary=salary,
            years_remaining=years,
            no_trade_clause=overall >= 47 and random.random() < 0.3
        )
        
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

def generate_database(config_name: str) -> League:
    """Generate a database using the specified configuration"""
    
    if config_name not in DATABASE_CONFIGURATIONS:
        raise ValueError(f"Unknown database configuration: {config_name}")
    
    config = DATABASE_CONFIGURATIONS[config_name]
    generator = DatabaseGenerator(config)
    
    return generator.generate_comprehensive_database()

def get_database_info(config_name: str) -> str:
    """Get detailed information about a database configuration"""
    
    if config_name not in DATABASE_CONFIGURATIONS:
        return "Unknown configuration"
    
    config = DATABASE_CONFIGURATIONS[config_name]
    
    info = f"""
{config.name}
{config.description}

Database Details:
• Total Players: {config.total_players:,}
• Draft Prospects: {config.prospects_per_draft} per year
• League Depth: {config.leagues_count} leagues with {config.minor_league_depth} levels
• International Diversity: {config.international_factor:.1f}x
• Veteran Balance: {config.veteran_distribution:.0%}
• Staff per Team: {config.staff_count}

Performance Impact: {"Low" if config.total_players < 15000 else "Medium" if config.total_players < 75000 else "High"}
Recommended for: {"Beginners" if config_name == "Small" else "Most players" if config_name == "Medium" else "Experienced managers" if config_name == "Large" else "Hardcore simulation fans"}
"""
    
    return info.strip()

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
