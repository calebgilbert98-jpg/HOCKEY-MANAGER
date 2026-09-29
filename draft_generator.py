# draft_generator.py
# Creates a new class of draft-eligible players with realistic archetypes and tiered potential.

import random
import math
from datetime import (timedelta, date)
from typing import (List, Tuple, Optional)
from game_classes import Player, PlayerPosition, GameBalance
import mesh_system

# --- Constants for Data Generation ---
# Using larger name pools makes for a more diverse game world.
# --- Name pools: nationality-first ---
# Every draft prospect gets a nationality FIRST (weighted below), then a
# first+last name drawn from that nation's authentic pool. All pools are
# stored ASCII-safe (see _to_ascii); get_random_name() normalizes defensively
# so odd characters can never crash generation.
FIRST_NAMES = {
    "Canada": ["Aiden", "Liam", "Noah", "Logan", "Ethan", "Jacob", "Nathan", "Connor", "William", "Jack", "Owen", "Ryan", "Matthew", "Shane", "Brandt", "Cole", "Mason", "Lucas", "Isaac", "Dylan", "Tyler", "Brayden", "Carter", "Nolan", "Gavin", "Dawson", "Brett", "Kyle", "Adam", "Sean"],
    "USA": ["Jackson", "Wyatt", "Carter", "Luke", "Brady", "Blake", "Hunter", "Zach", "Tyler", "Brock", "Chase", "Austin", "Cody", "Seth", "Trevor", "Jake", "Jeremy", "Cam", "Johnny", "Drew", "Logan", "Ryan", "Matt", "Nick", "Connor", "Dylan", "Kyle", "Alex", "Sam", "Will"],
    "Sweden": ["Erik", "Oscar", "Elias", "Anton", "Oliver", "William", "Filip", "Gustav", "Victor", "Emil", "Rasmus", "Lucas", "Nils", "Simon", "Marcus", "Joel", "Adam", "Jakob", "Linus", "Hampus", "Isak", "Hugo", "Melker", "Viggo", "Albin", "Casper", "Theo", "Wilmer"],
    "Finland": ["Mikko", "Kaapo", "Patrik", "Joonas", "Lauri", "Aleksi", "Ville", "Juuso", "Eero", "Eetu", "Valtteri", "Miro", "Juha", "Janne", "Teuvo", "Sami", "Jari", "Artturi", "Jesse", "Kasperi", "Olli", "Antti", "Topi", "Rasmus", "Leevi", "Niklas", "Saku", "Jesperi"],
    "Russia": ["Andrei", "Sergei", "Vladimir", "Alexander", "Ivan", "Dmitri", "Mikhail", "Nikita", "Evgeni", "Pavel", "Maxim", "Yuri", "Igor", "Kirill", "Fyodor", "Ilya", "Artem", "Slava", "Vasili", "Denis", "Daniil", "Matvei", "Yegor", "Timur", "Bogdan", "Arseny", "Vladislav", "Oleg"],
    "Czechia": ["Jakub", "Jan", "Tomas", "David", "Pavel", "Martin", "Filip", "Petr", "Jiri", "Dominik", "Radek", "Marek", "Michal", "Lukas", "Josef", "Roman", "Ondrej", "Daniel", "Karel", "Miroslav", "Vojtech", "Adam", "Simon", "Matej", "Krystof", "Stepan", "Vaclav", "Dalibor"],
    "Slovakia": ["Juraj", "Martin", "Tomas", "Peter", "Michal", "Lukas", "Marek", "Filip", "Samuel", "Adam", "Jakub", "David", "Oliver", "Simon", "Daniel", "Patrik", "Alex", "Tobias", "Richard", "Branislav", "Erik", "Ivan", "Jozef", "Kristian", "Matus", "Sebastian", "Viktor", "Andreas"],
    "Switzerland": ["Nico", "Nino", "Timo", "Kevin", "Marco", "Leon", "Luca", "Jonas", "Simon", "David", "Jan", "Lars", "Sven", "Roman", "Damien", "Tristan", "Andrea", "Gilles", "Noah", "Louis", "Yannick", "Reto", "Benjamin", "Dean", "Eliot", "Dario", "Sandro", "Fabian"],
    "Germany": ["Leon", "Moritz", "Tim", "Lukas", "Nico", "Dominik", "Philipp", "Jonas", "Maximilian", "Felix", "Tobias", "Jan", "Erik", "Simon", "David", "Paul", "Bennett", "Marc", "Alexander", "Daniel", "Kevin", "Dennis", "Marcel", "Tom", "Fabio", "Julian", "Niklas", "Henri"],
    "Latvia": ["Rodrigo", "Dans", "Zemgus", "Teodors", "Rihards", "Kristers", "Oskars", "Martins", "Janis", "Edgars", "Kaspars", "Andris", "Gints", "Maris", "Uvis", "Ralfs", "Roberts", "Arturs", "Emils", "Gustavs", "Daniels", "Rudolfs", "Sandis", "Elvis", "Ivars", "Haralds", "Renars", "Edzus"],
    "Slovenia": ["Anze", "Jan", "Rok", "Luka", "Gasper", "Tilen", "Miha", "Ziga"],
    "Norway": ["Mats", "Jonas", "Eskil", "Sander", "Andreas", "Martin", "Eirik", "Ludvig"],
    "Denmark": ["Nikolaj", "Lars", "Frederik", "Mikkel", "Oliver", "Mathias", "Jeppe", "Rasmus"],
    "Austria": ["Marco", "Thomas", "David", "Manuel", "Dominique", "Lukas", "Raphael", "Nico"],
    "France": ["Antoine", "Pierre", "Stephane", "Alexandre", "Hugo", "Valentin", "Louis", "Tim"],
    "Kazakhstan": ["Nikita", "Roman", "Dmitri", "Yevgeni", "Alexei", "Valeri", "Timur", "Anton"],
    "Belarus": ["Andrei", "Sergei", "Dmitri", "Alexei", "Yegor", "Vladislav", "Mikhail", "Artyom"],
    "Ukraine": ["Olexander", "Dmitri", "Bogdan", "Ruslan", "Vitali", "Andriy", "Igor", "Pavel"],
    "Italy": ["Marco", "Luca", "Matteo", "Andrea", "Davide", "Tommaso", "Diego", "Alex"],
    "Great Britain": ["Ben", "Liam", "Robert", "Jonathan", "Matthew", "Ollie", "Cade", "Logan"],
    "Japan": ["Yuto", "Shogo", "Kenta", "Ren", "Takumi", "Hiro", "Daichi", "Kaito"],
    "Australia": ["Jack", "Lachlan", "Cooper", "Riley", "Nathan", "Mitch", "Thomas", "Jayden"],
    "Netherlands": ["Daan", "Lars", "Jeroen", "Kevin", "Mike", "Jordy", "Raphael", "Stef"],
    "Hungary": ["Istvan", "Balazs", "Marton", "Vilmos", "Akos", "Gergo", "Csanad", "Adam"],
    "Lithuania": ["Tadas", "Mantas", "Ugnius", "Dovydas", "Paulius", "Arnoldas", "Emilijus", "Lukas"],
    "Poland": ["Bartosz", "Kamil", "Patryk", "Filip", "Mateusz", "Dominik", "Krystian", "Jakub"],
}

LAST_NAMES = {
    "Canada": ["Smith", "Brown", "Wilson", "Campbell", "Thompson", "MacDonald", "Clark", "Johnston", "Wright", "Dubois", "Roy", "Dube", "Lavoie", "Gagnon", "Bouchard", "Leblanc", "Gauthier", "Poulin", "Morin", "Cote", "Tremblay", "Pelletier", "Fortin", "Simard", "Lachance", "Couture", "Desjardins", "Charbonneau", "Beaulieu", "Fontaine", "Moreau", "Girard", "Lapointe", "Savard", "Boucher", "Caron", "Nadeau", "Paquette", "St-Pierre", "Martin", "Bernard", "Lefebvre", "Turcotte", "Ducharme", "Houle"],
    "USA": ["Johnson", "Miller", "Williams", "Jones", "Brown", "Davis", "Anderson", "Wilson", "Taylor", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Robinson", "Lewis", "Walker", "Young", "Allen", "King", "Wright", "Scott", "Green", "Baker", "Adams", "Nelson", "Carter", "Mitchell", "Perez", "Roberts", "Turner", "Phillips", "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart", "Morris", "Murphy", "Cook", "Rogers", "Morgan", "Bell"],
    "Sweden": ["Andersson", "Karlsson", "Nilsson", "Eriksson", "Larsson", "Olsson", "Lindqvist", "Petersson", "Svensson", "Gustafsson", "Lundqvist", "Nyqvist", "Hedman", "Ekman-Larsson", "Hornqvist", "Backstrom", "Silfverberg", "Zetterberg", "Hjalmarsson", "Ekholm", "Forsberg", "Sundin", "Lidstrom", "Alfredsson", "Naslund", "Samuelsson", "Franzen", "Kronwall", "Enstrom", "Steen", "Berglund", "Backlund", "Bratt", "Raymond", "Kempe", "Arvidsson", "Lindholm", "Rakell", "Johansson", "Klingberg", "Brodin", "Forsling", "Dahlin", "Karlstrom"],
    "Finland": ["Koivu", "Laine", "Rantanen", "Ristolainen", "Lindell", "Barkov", "Granlund", "Haula", "Donskoi", "Armia", "Nieminen", "Lehkonen", "Heiskanen", "Lankinen", "Rinne", "Rask", "Saros", "Heinola", "Teravainen", "Kakko", "Selanne", "Kurri", "Tikkanen", "Numminen", "Timonen", "Kiprusoff", "Lehtonen", "Niemi", "Filppula", "Jokinen", "Korpikoski", "Pulkkinen", "Vatanen", "Maatta", "Nutivaara", "Honka", "Puljujarvi", "Kotkaniemi", "Hintz", "Lundell", "Tolvanen", "Kupari", "Maccelli", "Luostarinen"],
    "Russia": ["Ovechkin", "Malkin", "Kuznetsov", "Tarasenko", "Kucherov", "Vasilevskiy", "Bobrovsky", "Panarin", "Svechnikov", "Zadorov", "Provorov", "Zaitsev", "Orlov", "Podkolzin", "Romanov", "Kaprizov", "Kravtsov", "Shesterkin", "Sorokin", "Askarov", "Datsyuk", "Fedorov", "Bure", "Mogilny", "Larionov", "Fetisov", "Kovalev", "Zubov", "Gonchar", "Markov", "Kulikov", "Voynov", "Emelin", "Nikulin", "Tyutin", "Volchenkov", "Medvedev", "Marchenko", "Michkov", "Voronkov", "Chinakhov", "Kostin", "Barbashev", "Trenin"],
    "Czechia": ["Necas", "Palat", "Voracek", "Krejci", "Kase", "Zadina", "Hronek", "Chytil", "Jaskin", "Faksa", "Zacha", "Polak", "Gudas", "Radil", "Simon", "Nosek", "Frk", "Sustr", "Rutta", "Jerabek", "Jagr", "Hasek", "Elias", "Nedved", "Straka", "Hejduk", "Prospal", "Sykora", "Kubina", "Zidlicky", "Spacek", "Kaberle", "Rozsival", "Vokoun", "Pavelec", "Mrazek", "Francouz", "Vejmelka", "Dostal", "Rittich", "Hertl", "Vrana", "Kubalik", "Suchanek"],
    "Slovakia": ["Chara", "Hossa", "Gaborik", "Demitra", "Satan", "Bondra", "Palffy", "Stumpel", "Nagy", "Handzus", "Visnovsky", "Meszaros", "Sekera", "Tatar", "Panik", "Cernak", "Fehervary", "Slafkovsky", "Nemec", "Ruzicka", "Hudacek", "Budaj", "Halak", "Laco", "Janus", "Dano", "Hrivik", "Cibak", "Sersen", "Starosta", "Valach", "Mihalik", "Granak", "Baranka", "Jurcina", "Lintner", "Kollar", "Bartovic", "Zednik", "Marincin", "Cajkovsky", "Cehlarik", "Lunter", "Skalicky"],
    "Switzerland": ["Josi", "Niederreiter", "Meier", "Hischier", "Fiala", "Streit", "Sbisa", "Diaz", "Bartschi", "Brunner", "Wick", "Ambuhl", "Pluss", "Seger", "Blindenbacher", "Vauclair", "Forster", "Grossmann", "Du Bois", "Hollenstein", "Rufenacht", "Suri", "Bodenmann", "Martschini", "Malgin", "Moser", "Kukan", "Siegenthaler", "Muller", "Schmid", "Aeschlimann", "Berra", "Hiller", "Gerber", "Aebischer", "Genoni", "Mayer", "Rathgeb", "Untersander", "Heldner", "Geisser", "Egli", "Leuenberger", "Rod"],
    "Germany": ["Draisaitl", "Seider", "Stutzle", "Peterka", "Reichel", "Sturm", "Ehrhoff", "Kahun", "Greiss", "Gogulla", "Hager", "Mauer", "Wolf", "Ehliz", "Plachta", "Tiffels", "Kastner", "Nowak", "Abeltshauser", "Brandt", "Daschner", "Wissmann", "Muller", "Fischbuch", "Pfoderl", "Loibl", "Eder", "Kink", "Schutz", "Hordler", "Uvira", "Pietta", "Akdag", "Hospelt", "Furchner", "Ullmann", "Felski", "Sulzer", "Holzer", "Rankel", "Baxmann", "Krueger", "Tripp", "Pielmeier"],
    "Latvia": ["Girgensons", "Daugavins", "Kenins", "Kulda", "Bartulis", "Sotnieks", "Redlihs", "Freibergs", "Cibulskis", "Balinskis", "Jaks", "Rubins", "Zile", "Punnenovs", "Gudlevskis", "Merzlikins", "Silovs", "Abols", "Balcers", "Dzierkals", "Buncis", "Mamcics", "Jerofejevs", "Sprukts", "Vasiljevs", "Ozolins", "Irbe", "Skrastins", "Ankipans", "Cipulis", "Saulietis", "Berzins", "Sirokovs", "Upitis", "Kalnins", "Masalskis", "Muiznieks", "Lavins", "Dzerins", "Tribuncovs", "Galvins", "Andersons", "Bukarts", "Lipsbergs"],
    "Slovenia": ["Kopitar", "Mursak", "Jeglic", "Urbas", "Verlic", "Sabolic", "Ograjensek", "Podlipnik", "Pintaric", "Kranjc"],
    "Norway": ["Zuccarello", "Thoresen", "Olimb", "Holos", "Martinsen", "Bonsaksen", "Sorvik", "Roymark", "Bastiansen", "Spets"],
    "Denmark": ["Ehlers", "Bjorkstrand", "Andersen", "Eller", "Hansen", "Jensen", "Nielsen", "Larsen", "Storm", "Boedker"],
    "Austria": ["Vanek", "Raffl", "Grabner", "Pock", "Nodl", "Trattnig", "Koch", "Heinrich", "Schlacher", "Kaspitz"],
    "France": ["Roussel", "Bellemare", "Da Costa", "Auvitu", "Janil", "Perret", "Bertrand", "Rech", "Claireaux", "Ritz"],
    "Kazakhstan": ["Antipin", "Mikhailis", "Shestakov", "Savchenko", "Starchenko", "Rymarev", "Zhailauov", "Krasnoslobodtsev", "Polokhov", "Shalapov"],
    "Belarus": ["Grabovski", "Kostitsyn", "Kolosov", "Gotovets", "Kovyrshin", "Demkov", "Sharangovich", "Protas", "Solovyov", "Khenkel"],
    "Ukraine": ["Fedotenko", "Ponikarovsky", "Zherdev", "Babchuk", "Mikhnov", "Blagy", "Materukhin", "Varlamov", "Shakhvorostov", "Tymchenko"],
    "Italy": ["Frigo", "Kostner", "Bernard", "Gander", "Insam", "Hofer", "Traversa", "Morini", "Glira", "Pietroniro"],
    "Great Britain": ["Bowns", "Perlini", "Mosey", "Davies", "Richardson", "Dowd", "Lachowicz", "Phillips", "O'Connor", "Betteridge"],
    "Japan": ["Tanaka", "Suzuki", "Sato", "Yamamoto", "Kobayashi", "Nakamura", "Ito", "Watanabe", "Hitosato", "Terao"],
    "Australia": ["Walker", "Darge", "Humphries", "Todd", "Powell", "Webster", "Clark", "Harvey", "Cox", "Bell"],
    "Netherlands": ["van der Velden", "de Jong", "Jansen", "van Dijk", "Bakker", "Visser", "Smit", "Meijer", "de Boer", "Mulder"],
    "Hungary": ["Gallo", "Sofron", "Vas", "Bartalis", "Sarauer", "Erdely", "Nagy", "Sebok", "Horvath", "Stipsicz"],
    "Lithuania": ["Bosas", "Kumeliauskas", "Bogdziul", "Katulis", "Alisauskas", "Gintautas", "Nekrasevicius", "Rumsevicius"],
    "Poland": ["Pasiut", "Dziubinski", "Wanat", "Kolusz", "Bryk", "Ciura", "Kapica", "Laszkiewicz"],
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
    "Czechia": [
        "Prague", "Brno", "Ostrava", "Kladno", "Plzen",
        "Liberec", "Olomouc", "Pardubice", "Zlin", "Karlovy Vary"
    ],
    "Slovakia": [
        "Bratislava", "Kosice", "Trencin", "Zilina", "Poprad",
        "Nitra", "Banska Bystrica", "Martin"
    ],
    "Switzerland": [
        "Bern", "Zurich", "Geneva", "Lausanne", "Davos",
        "Fribourg", "Lugano", "St. Gallen"
    ],
    "Germany": [
        "Berlin", "Munich", "Cologne", "Dusseldorf", "Mannheim",
        "Hamburg", "Nuremberg", "Augsburg"
    ],
    "Latvia": [
        "Riga", "Liepaja", "Daugavpils", "Jelgava", "Ventspils", "Ogre"
    ],
    "Slovenia": ["Ljubljana", "Jesenice", "Bled", "Kranj"],
    "Norway": ["Oslo", "Stavanger", "Bergen", "Trondheim"],
    "Denmark": ["Copenhagen", "Herning", "Aalborg", "Rodovre"],
    "Austria": ["Vienna", "Graz", "Salzburg", "Innsbruck", "Klagenfurt"],
    "France": ["Paris", "Lyon", "Grenoble", "Rouen", "Amiens"],
    "Kazakhstan": ["Astana", "Almaty", "Karaganda", "Ust-Kamenogorsk"],
    "Belarus": ["Minsk", "Grodno", "Gomel", "Vitebsk"],
    "Ukraine": ["Kyiv", "Kharkiv", "Donetsk", "Odesa"],
    "Italy": ["Milan", "Bolzano", "Asiago", "Cortina"],
    "Great Britain": ["London", "Nottingham", "Sheffield", "Belfast", "Cardiff"],
    "Japan": ["Tokyo", "Osaka", "Sapporo", "Nagoya"],
    "Australia": ["Sydney", "Melbourne", "Perth", "Brisbane"],
    "Netherlands": ["Amsterdam", "Rotterdam", "The Hague", "Tilburg"],
    "Hungary": ["Budapest", "Szekesfehervar", "Miskolc", "Debrecen"],
    "Lithuania": ["Vilnius", "Kaunas", "Klaipeda", "Elektrenai"],
    "Poland": ["Warsaw", "Krakow", "Katowice", "Tychy", "Gdansk"],
}

# Legacy aliases: older callers may pass "Czech"/"Other" (pre-rename keys).
FIRST_NAMES["Czech"] = FIRST_NAMES["Czechia"]
LAST_NAMES["Czech"] = LAST_NAMES["Czechia"]
BIRTHPLACES["Czech"] = BIRTHPLACES["Czechia"]
FIRST_NAMES["Other"] = FIRST_NAMES["Slovenia"] + FIRST_NAMES["Norway"]
LAST_NAMES["Other"] = LAST_NAMES["Slovenia"] + LAST_NAMES["Norway"]
BIRTHPLACES["Other"] = BIRTHPLACES["Slovenia"] + BIRTHPLACES["Norway"]


def _to_ascii(name: str) -> str:
    """Transliterate a name to ASCII-safe text (s->s, c->c, z->z, a->a,
    o->o, u->u, e->e, ...). Never raises on odd characters."""
    import unicodedata
    try:
        return unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    except Exception:
        return "".join(ch for ch in str(name) if ord(ch) < 128)


# --- Nationality weights (real-draft-like) ---
# Big-10 nations sum to 95.5%; the 16-nation obscure pool splits the remaining
# 4.5% evenly (~0.28% each), matching real drafts' long tail of one-offs.
NATIONALITY_WEIGHTS = {
    "Canada": 0.40,
    "USA": 0.25,
    "Sweden": 0.08,
    "Finland": 0.06,
    "Russia": 0.06,
    "Czechia": 0.03,
    "Slovakia": 0.02,
    "Switzerland": 0.02,
    "Germany": 0.02,
    "Latvia": 0.015,
}
_OBSCURE_NATIONS = [
    "Slovenia", "Norway", "Denmark", "Austria", "France", "Kazakhstan",
    "Belarus", "Ukraine", "Italy", "Great Britain", "Japan", "Australia",
    "Netherlands", "Hungary", "Lithuania", "Poland",
]
for _on in _OBSCURE_NATIONS:
    NATIONALITY_WEIGHTS[_on] = 0.045 / len(_OBSCURE_NATIONS)
del _on

# North-American nationalities: the 20-year-old age-out rule applies to these.
_NA_NATIONALITIES = frozenset({"Canada", "USA"})

# --- Junior leagues by nationality (plain strings; formal rights fields land
# in game_classes.py via another worker) ---
JUNIOR_LEAGUES = {
    "Canada": ["OHL", "QMJHL", "WHL"],
    "USA": ["USHL", "NTDP", "NCAA"],
    "Sweden": ["J20 Nationell", "SHL"],
    "Finland": ["U20 SM-sarja", "Liiga"],
    "Russia": ["MHL", "KHL"],
    "Czechia": ["Czech U20", "Extraliga"],
    "Slovakia": ["Slovak U20", "Extraliga"],
    "Switzerland": ["U20-Elit", "NL"],
    "Germany": ["DNL", "DEL"],
    "Latvia": ["MHL", "Latvian league"],
    "Slovenia": ["AlpsHL", "ICEHL"],
    "Norway": ["Eliteserien", "MHL"],
    "Denmark": ["Metal Ligaen", "J20 Nationell"],
    "Austria": ["AlpsHL", "ICEHL"],
    "France": ["Ligue Magnus", "MHL"],
    "Kazakhstan": ["MHL", "KHL"],
    "Belarus": ["Belarus Extraliga", "MHL"],
    "Ukraine": ["UHL", "MHL"],
    "Italy": ["AlpsHL", "ICEHL"],
    "Great Britain": ["EIHL", "NIHL"],
    "Japan": ["Asia League", "JIHF"],
    "Australia": ["AIHL", "ECSL"],
    "Netherlands": ["BeNeLiga", "Eredivisie"],
    "Hungary": ["Erste Liga", "MHL"],
    "Lithuania": ["Baltic League", "MHL"],
    "Poland": ["PHL", "MHL"],
}

# --- Goalie generation parameters (Task E) ---
# GOALIE_SHARE: POSITION_DISTRIBUTION goalie weight 0.06 + floor 18 -> ~23
#   of 224 (real drafts take ~20-25 goalies). Position floor is 18.
# GOALIE_BASE_RANGE (20, 58) vs skater (24, 60): lower floor, wider spread.
# GOALIE_RAWNESS_RANGE (0.85, 0.97): multiplier on a goalie's CURRENT
#   goalie-specific attributes at generation. Ceilings (grade-driven archetype
#   boosts) are untouched, so goalies carry a WIDER current-vs-potential gap
#   than skaters -- lower floors, similar ceilings.
# GOALIE_GEM_BOOM_PROB 0.06 / GOALIE_GEM_BUST_PROB 0.08: pre-seed_true_potential
#   fat-tail roll for goalies -- higher boom AND higher bust probability than
#   the flat gem table skaters use (fatter tails, not a flat low ceiling).
# GUARANTEED_GOALIE_GEMS: 1-2 per class, drawn from rank 65+ (round 3+)
#   goalies, true grade bumped up to +2 (capped per grade), flagged via
#   player.hidden_gem = True so late-round goalie steals actually occur.
GOALIE_BASE_RANGE = (20, 58)
GOALIE_RAWNESS_RANGE = (0.85, 0.97)
GOALIE_GEM_BOOM_PROB = 0.06
GOALIE_GEM_BUST_PROB = 0.08
_GEM_BUMP_CAP = {"F": 3, "D": 3, "D+": 2, "C-": 2, "C": 2,
                 "C+": 1, "B-": 1, "B": 1}  # mirrors prospect_development


def _assign_junior_league(nationality: str) -> str:
    """Plausible junior/pro development league for a prospect's nationality."""
    return random.choice(JUNIOR_LEAGUES.get(nationality, ["MHL", "Junior league"]))

# --- Player Archetypes ---
# Defines the attribute ranges for different player types. This makes balancing easier.
ARCHETYPES = {
    "FORWARDS": {
        "Sniper": {
            "description": "An elite goal-scorer with exceptional shooting skills",
            "attributes": {
                "shooting": (28, 40), 
                "offensive_awareness": (24, 36), 
                "deking": (22, 34),
                "shooting_accuracy": (28, 40),
                "vision": (20, 32)
            },
            "tendency": {"shooting_tendency": (70, 90), "hitting_tendency": (20, 50)}
        },
        "Playmaker": {
            "description": "A creative passer who excels at setting up teammates",
            "attributes": {
                "passing": (28, 40), 
                "vision": (26, 38), 
                "offensive_awareness": (24, 34),
                "puck_control": (24, 34),
                "deking": (22, 32)
            },
            "tendency": {"shooting_tendency": (20, 40), "hitting_tendency": (10, 40)}
        },
        "Power Forward": {
            "description": "A physical forward who combines size with scoring ability",
            "attributes": {
                "strength": (28, 38), 
                "checking": (26, 36), 
                "shooting": (22, 32),
                "stamina": (24, 34),
                "puck_protection": (24, 34)
            },
            "tendency": {"shooting_tendency": (50, 70), "hitting_tendency": (70, 90)}
        },
        "Two-Way Forward": {
            "description": "A balanced player who contributes at both ends of the ice",
            "attributes": {
                "defensive_awareness": (26, 34), 
                "teamwork": (24, 34), 
                "faceoffs": (20, 32),
                "skating": (22, 32),
                "discipline": (24, 32)
            },
            "tendency": {"shooting_tendency": (40, 60), "hitting_tendency": (40, 60)}
        },
        "Grinder": {
            "description": "A hard-working, physical player who excels along the boards",
            "attributes": {
                "determination": (26, 36), 
                "strength": (24, 34), 
                "checking": (24, 34),
                "puck_protection": (22, 32),
                "stamina": (26, 34)
            },
            "tendency": {"shooting_tendency": (30, 50), "hitting_tendency": (60, 90)}
        },
        "Skilled Finesse": {
            "description": "A highly skilled player with exceptional stickhandling",
            "attributes": {
                "deking": (28, 38), 
                "puck_control": (26, 36), 
                "flair": (26, 36),
                "skating": (24, 34),
                "vision": (22, 32)
            },
            "tendency": {"shooting_tendency": (40, 70), "hitting_tendency": (10, 30)}
        },
        "Enforcer": {
            "description": "The toughest player on the ice. Protects teammates, punishes opponents",
            "attributes": {
                "strength": (28, 38), \
                "aggressiveness": (26, 36), \
                "checking": (24, 34),
                "durability": (24, 34), \
                "discipline": (10, 20)
            },
            "tendency": {"shooting_tendency": (20, 40), "hitting_tendency": (80, 100)}
        }
    },
    "DEFENSEMEN": {
        "Offensive Defenseman": {
            "description": "A mobile defenseman who contributes offensively",
            "attributes": {
                "skating": (26, 36), 
                "passing": (24, 34), 
                "offensive_awareness": (24, 32),
                "shooting": (22, 32),
                "vision": (20, 32)
            },
            "tendency": {"shooting_tendency": (50, 70), "hitting_tendency": (30, 60)}
        },
        "Defensive Defenseman": {
            "description": "A stay-at-home defender who excels in his own zone",
            "attributes": {
                "checking": (26, 36), 
                "strength": (24, 34), 
                "defensive_awareness": (26, 36),
                "discipline": (22, 32),
                "shot_blocking": (24, 34)
            },
            "tendency": {"shooting_tendency": (20, 40), "hitting_tendency": (60, 80)}
        },
        "Two-Way Defenseman": {
            "description": "A balanced defender who contributes at both ends",
            "attributes": {
                "defensive_awareness": (24, 32), 
                "skating": (22, 32), 
                "passing": (20, 30),
                "checking": (22, 32),
                "shot_blocking": (22, 32)
            },
            "tendency": {"shooting_tendency": (30, 60), "hitting_tendency": (40, 70)}
        },
        "Physical Defenseman": {
            "description": "An intimidating defender who plays a punishing style",
            "attributes": {
                "strength": (28, 38), 
                "checking": (26, 36), 
                "shot_blocking": (24, 34),
                "stamina": (22, 32),
                "discipline": (16, 26)
            },
            "tendency": {"shooting_tendency": (20, 40), "hitting_tendency": (70, 90)}
        },
        "Puck-Moving Defenseman": {
            "description": "A defender who excels at transitioning the puck",
            "attributes": {
                "passing": (26, 36), 
                "puck_control": (24, 34), 
                "vision": (24, 34),
                "skating": (24, 34),
                "defensive_awareness": (20, 30)
            },
            "tendency": {"shooting_tendency": (30, 50), "hitting_tendency": (20, 50)}
        }
    },
    "GOALIES": {
        "Butterfly Goalie": {
            "description": "A technical goalie who excels at covering the lower net",
            "attributes": {
                "goaltending": (24, 36), 
                "reflexes": (22, 34),
                "positioning": (24, 36),
                "rebound_control": (20, 32),
                "puck_handling": (14, 28)
            }
        },
        "Hybrid Goalie": {
            "description": "A versatile goalie who combines different styles",
            "attributes": {
                "goaltending": (24, 34), 
                "reflexes": (24, 34),
                "positioning": (22, 32),
                "rebound_control": (22, 32),
                "puck_handling": (20, 30)
            }
        },
        "Athletic Goalie": {
            "description": "A dynamic goalie who relies on athleticism and reflexes",
            "attributes": {
                "goaltending": (22, 32), 
                "reflexes": (28, 38),
                "positioning": (20, 30),
                "rebound_control": (18, 28),
                "puck_handling": (18, 30)
            }
        },
        "Puck-Handling Goalie": {
            "description": "A goalie who excels at playing the puck",
            "attributes": {
                "goaltending": (22, 32), 
                "reflexes": (20, 32),
                "positioning": (22, 32),
                "rebound_control": (20, 30),
                "puck_handling": (28, 38)
            }
        }
    }
}

# --- League and Draft Settings ---
# Positioning split by archetype (2026-09-28, per Muck): every skater
# prospect rolls offensive_positioning (getting open, net-front spot wins,
# shot quality) and defensive_positioning (gap control, box-outs, blocks,
# takeaways) from their archetype. Ranges are 20-scale, applied with the
# same x2.0 x potential_factor conversion as archetype attributes below.
# Goalies keep the single `positioning` (crease) -- no split.
_ARCHETYPE_POSITIONING_SPLIT = {
    # archetype: ((off_lo, off_hi), (def_lo, def_hi))
    "Sniper":               ((30, 40), (18, 26)),
    "Playmaker":            ((28, 38), (20, 28)),
    "Power Forward":        ((26, 36), (20, 28)),
    "Two-Way Forward":      ((24, 34), (28, 38)),
    "Grinder":              ((18, 28), (24, 34)),
    "Skilled Finesse":      ((28, 38), (18, 26)),
    "Enforcer":             ((14, 24), (20, 30)),
    "Offensive Defenseman": ((26, 36), (20, 30)),
    "Defensive Defenseman": ((16, 26), (30, 40)),
    "Two-Way Defenseman":   ((24, 32), (28, 36)),
    "Physical Defenseman":  ((16, 26), (28, 38)),
    "Puck-Moving Defenseman": ((24, 34), (22, 32)),
}
# Nationality-first weights (real-draft-like). COUNTRY_DISTRIBUTION is the
# name older callers (get_random_nationality, player_generator) use.
COUNTRY_DISTRIBUTION = dict(NATIONALITY_WEIGHTS)

POSITION_DISTRIBUTION = {
    PlayerPosition.CENTER: 0.215,
    PlayerPosition.LEFT_WING: 0.186,
    PlayerPosition.RIGHT_WING: 0.186,
    PlayerPosition.LEFT_DEFENSE: 0.157,
    PlayerPosition.RIGHT_DEFENSE: 0.156,
    # Real drafts take ~20-25 goalies of 224. Floor 18 + 0.06 share -> ~23.
    PlayerPosition.GOALIE: 0.06
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

# Draft class quality presets. "Normal" is the baseline above (~1 generational,
# ~11 elite/top-line per 224 picks, matching real NHL draft hit rates).
# Other presets shift probability mass up/down the potential ladder.
DRAFT_QUALITY_DISTRIBUTIONS = {
    "Weak": {
        "A+": 0.001, "A": 0.005, "A-": 0.010,
        "B+": 0.020, "B": 0.050, "B-": 0.100,
        "C+": 0.150, "C": 0.220, "C-": 0.200,
        "D": 0.150, "F": 0.094,
    },
    "Normal": POTENTIAL_DISTRIBUTION,
    "Strong": {
        "A+": 0.010, "A": 0.030, "A-": 0.060,
        "B+": 0.080, "B": 0.120, "B-": 0.150,
        "C+": 0.150, "C": 0.180, "C-": 0.120,
        "D": 0.070, "F": 0.030,
    },
    "Generational": {
        # A 2023 (Bedard) or 2015 (McDavid/Eichel) type draft: multiple
        # franchise talents at the top, deep through the first two rounds.
        "A+": 0.020, "A": 0.040, "A-": 0.080,
        "B+": 0.100, "B": 0.120, "B-": 0.140,
        "C+": 0.140, "C": 0.160, "C-": 0.100,
        "D": 0.070, "F": 0.030,
    },
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
    """Returns a random first and last name appropriate for the given country.
    Names are normalized to ASCII-safe text (transliteration safety net).

    Star surnames are filtered (playtest P-5, via name_safety): the pools
    keep real hockey surnames for national authenticity, but a generated
    prospect never borrows a recognizable real player's surname.
    """
    first_name = random.choice(FIRST_NAMES.get(country, FIRST_NAMES["Other"]))
    # P-5: star-surname filter (Caleb's name_safety) -- generated prospects
    # must not borrow a recognizable real player's surname.
    try:
        import name_safety as _ns
        last_name = _ns.pick_surname(LAST_NAMES.get(country, LAST_NAMES["Other"]))
    except Exception:
        last_name = random.choice(LAST_NAMES.get(country, LAST_NAMES["Other"]))
    return _to_ascii(first_name), _to_ascii(last_name)


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

def get_random_potential(distribution=None) -> str:
    """Returns a randomly selected potential grade based on probability distribution."""
    dist = distribution or POTENTIAL_DISTRIBUTION
    potentials = list(dist.keys())
    probabilities = list(dist.values())
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

def get_base_attribute_value(min_val: int = 10, max_val: int = 30) -> int:
    """
    Generate a base attribute value following a normal distribution.
    Most values will be around the middle of the range.
    (100-scale: callers pass doubled ranges)"""
    mean = (min_val + max_val) / 2
    std_dev = (max_val - min_val) / 4  # This gives a reasonable spread
    value = int(random.normalvariate(mean, std_dev))
    return max(min_val, min(max_val, value))

def calculate_draft_ranking(player: Player) -> float:
    """Calculate a draft ranking score for a player based on attributes and potential."""
    # Convert potential grade to numeric value
    potential_values = {
        "A+": 99, "A": 96, "A-": 92,
        "B+": 88, "B": 84, "B-": 80,
        "C+": 76, "C": 72, "C-": 68,
        "D": 60, "F": 50
    }
    potential_value = potential_values.get(player.potential_grade, 65)
    
    # Get current overall rating
    current_rating = player.overall_rating()
    
    # Calculate ranking score with some randomness
    ranking_score = (current_rating * 0.7) + (potential_value * 0.3)
    
    # Add some randomness to simulate scouting variance
    ranking_score += random.uniform(-5, 5)
    
    return ranking_score


# --- Draft eligibility (real NHL rules) ---

def is_draft_eligible(birthdate, nationality, draft_year) -> bool:
    """Real NHL draft eligibility (with the game's Euro overager tweak).

    birthdate: "YYYY-MM-DD" string. draft_year: the June draft year (int).
    - Eligible iff the player turns 18 on/before Sept 15 of draft_year
      (birthdate <= (draft_year-18)-09-15).
    - North Americans (Canada, USA) age out at 20: must be born on/after
      Sept 16 of (draft_year - 21). A 21-year-old NA is NOT eligible
      (becomes a UFA; never draft-eligible again).
    - Europeans age out at 22: must be born on/after Sept 16 of
      (draft_year - 23). A 23+ Euro loses draft eligibility and becomes
      directly signable as a free agent (the undrafted-import path).
    Malformed input -> False (defensive).
    """
    try:
        if not isinstance(birthdate, str):
            return False
        parts = birthdate.strip().split("-")
        if len(parts) != 3:
            return False
        born = date(int(parts[0]), int(parts[1]), int(parts[2]))
        draft_year = int(draft_year)
    except (ValueError, TypeError, AttributeError):
        return False
    # Younger edge: must turn 18 on/before Sept 15 of the draft year,
    # i.e. born on/before Sept 15 eighteen years earlier.
    if born > date(draft_year - 18, 9, 15):
        return False
    # Older edge: NA born on/after Sept 16 of draft_year - 21 (20 max);
    # Europeans born on/after Sept 16 of draft_year - 23 (22 max).
    if (nationality or "") in _NA_NATIONALITIES:
        if born < date(draft_year - 21, 9, 16):
            return False
    else:
        if born < date(draft_year - 23, 9, 16):
            return False
    return True


def player_locked_by_draft(player, draft_year=None) -> bool:
    """True if signing this player as a free agent would sidestep the draft.

    Draft-eligible players are locked: they can only change clubs via the
    draft, never via direct free-agent signing. draft_year defaults to the
    upcoming June draft. Malformed/missing data -> False (never lock on a
    guess).
    """
    try:
        if draft_year is None:
            draft_year = _default_draft_year()
        return bool(is_draft_eligible(
            getattr(player, "birth_date", ""),
            getattr(player, "nationality", ""),
            draft_year))
    except Exception:
        return False


def age_on_sept15(birthdate, draft_year) -> Optional[int]:
    """Age (whole years) on Sept 15 of draft_year. None if malformed."""
    try:
        if not isinstance(birthdate, str):
            return None
        parts = birthdate.strip().split("-")
        if len(parts) != 3:
            return None
        born = date(int(parts[0]), int(parts[1]), int(parts[2]))
        draft_year = int(draft_year)
    except (ValueError, TypeError, AttributeError):
        return None
    age = draft_year - born.year
    if (born.month, born.day) > (9, 15):
        age -= 1
    return age


def _default_draft_year() -> int:
    """Next June draft derived from today's date: if month >= 7 the upcoming
    draft is next year's, otherwise it's this year's."""
    today = date.today()
    return today.year + 1 if today.month >= 7 else today.year


def _random_birthdate_for_age(age: int, nationality: str, draft_year: int) -> str:
    """Random "YYYY-MM-DD" birthdate making the player exactly `age` on
    Sept 15 of draft_year, inside the is_draft_eligible window. age 21+ is
    only valid for non-North-American nationalities (NA players age out
    at 20); age 23+ is invalid for everyone (Europeans age out at 22);
    a ValueError is raised otherwise."""
    if age >= 21 and (nationality or "") in _NA_NATIONALITIES:
        raise ValueError(f"NA prospect cannot be {age} in the {draft_year} draft")
    if age >= 23:
        raise ValueError(f"Prospect cannot be {age} in the {draft_year} draft"
                         " (Europeans age out at 22)")
    start = date(draft_year - age - 1, 9, 16)
    end = date(draft_year - age, 9, 15)
    # Defensive clamp to the NA upper bound in case of rounding drift.
    if (nationality or "") in _NA_NATIONALITIES:
        na_floor = date(draft_year - 21, 9, 16)
        if start < na_floor:
            start = na_floor
    born = start + timedelta(days=random.randint(0, (end - start).days))
    return born.isoformat()


def _roll_prospect_age() -> int:
    """Draft-class age mix: mostly 18, some 19, a few 20, rare 21-22
    European overagers (handled by the caller forcing a non-NA nationality)."""
    r = random.random()
    if r < 0.72:
        return 18
    if r < 0.90:
        return 19
    if r < 0.97:
        return 20
    return random.randint(21, 22)


def _random_european_nationality() -> str:
    """Non-North-American nationality, weighted by NATIONALITY_WEIGHTS."""
    pool = [(n, w) for n, w in NATIONALITY_WEIGHTS.items()
            if n not in _NA_NATIONALITIES]
    nations, weights = zip(*pool)
    return random.choices(nations, weights=weights, k=1)[0]


def _grade_ladder_index(grade: str) -> int:
    """Index of a potential grade on the F..A+ ladder (local copy so this
    module never hard-depends on prospect_development at import time)."""
    ladder = ["F", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]
    g = (grade or "C").strip()
    if g not in ladder:
        g = g[:1] if g[:1] in ladder else "C"
        if g not in ladder:
            g = "C"
    return ladder.index(g)


def _grade_ladder() -> list:
    return ["F", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]


def create_prospect(age: int = 18, 
                   position: Optional[PlayerPosition] = None, 
                   potential: Optional[str] = None,
                   nationality: Optional[str] = None,
                   potential_distribution=None,
                   draft_year: Optional[int] = None,
                   personality_tilt: Optional[str] = None) -> Player:
    """
    Create a new prospect with the specified parameters.
    If parameters are not provided, they will be randomly generated.
    potential_distribution: override the potential grade distribution
        (used for draft class quality settings).
    draft_year: the June draft this prospect is eligible for; defaults to the
        next June draft derived from today's date. Birthdate is drawn from the
        window that makes the prospect exactly `age` on Sept 15 of draft_year,
        so birth_date/age always agree with is_draft_eligible().
    personality_tilt: this draft class's character ("fiery", "circus",
        "sulky", "professional", or None) -- leans the personality-blend
        odds so each class has its own temperament.
    """
    # Determine nationality if not specified
    if nationality is None:
        nationality = get_random_nationality()

    if draft_year is None:
        draft_year = _default_draft_year()
    
    # Get a name appropriate for the nationality
    first_name, last_name = get_random_name(nationality)
    birthplace = get_random_birthplace(nationality)
    
    # Determine position if not specified
    if position is None:
        position = get_random_position()
    
    # Determine potential if not specified
    if potential is None:
        potential = get_random_potential(potential_distribution)
    
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
    # Note: player.development_arc was rolled at Player() creation as pure
    # individual variance, deliberately independent of grade/draft position --
    # no prospect is locked into a pathway (Muck: the Zetterberg/Datsyuk/
    # Kucherov element is the whole point).
    
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
    
    # Birth and draft information for prospects. The birthdate is drawn from
    # the window that makes the prospect exactly `age` on Sept 15 of
    # draft_year, so birth_date/age always satisfy is_draft_eligible().
    player.birth_date = _random_birthdate_for_age(age, nationality, draft_year)
    player.draft_year = draft_year
    player.draft_position = "Prospect"  # Will be set after draft

    # Junior/pro development league, consistent with nationality (plain
    # attribute; formal rights fields are added in game_classes.py).
    player.junior_league = _assign_junior_league(nationality)
    
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
    
    # Set EVERY overall-relevant attribute explicitly at prospect range.
    # (Dataclass defaults are valid 100-scale adult fallbacks; prospects must
    # never inherit them — an 18-year-old is not an NHL-average player.)
    _PROSPECT_BASE_ATTRS = [
        'skating', 'shooting', 'passing', 'checking', 'faceoffs', 'faceoff_wins',
        'determination', 'teamwork', 'leadership', 'discipline', 'flair',
        'offensive_awareness', 'defensive_awareness', 'deking', 'strength',
        'vision', 'stickhandling', 'shooting_accuracy', 'shooting_power',
        'passing_accuracy', 'passing_creativity', 'puck_protection', 'stamina',
        'shot_blocking', 'hockey_iq', 'composure', 'aggressiveness', 'work_rate',
        'anticipation', 'decision_making', 'focus', 'confidence', 'acceleration',
        'balance', 'endurance', 'agility', 'speed', 'durability', 'off_the_puck',
        'wristshot', 'slapshot', 'pokecheck', 'bodycheck', 'one_timer',
        'backhand', 'screen_shots', 'loose_puck', 'creativity', 'pressure_player',
        'puck_control',
    ]
    for attr in _PROSPECT_BASE_ATTRS:
        setattr(player, attr, get_base_attribute_value(24, 60))

    # Set goalie-specific attributes. Goalies roll a lower, wider base range
    # than skaters (GOALIE_BASE_RANGE): lower floors, similar ceilings.
    if position == PlayerPosition.GOALIE:
        _glo, _ghi = GOALIE_BASE_RANGE
        for attr in ['goaltending', 'reflexes', 'positioning', 'rebound_control',
                     'puck_handling', 'glove_hand', 'stick_side', 'breakaway_skill']:
            setattr(player, attr, get_base_attribute_value(_glo, _ghi))
    
    # Set tendencies with defaults
    player.shooting_tendency = random.randint(30, 70)
    player.hitting_tendency = random.randint(30, 70)
    
    # Apply the archetype-specific attribute modifiers
    for attr, (min_val, max_val) in archetype_data.get("attributes", {}).items():
        # Get a random value in the archetype's range
        value = random.randint(min_val, max_val)
        # Apply potential-based adjustment (better potential = higher chance of good attributes)
        # Archetype ranges are doubled 20-scale values; x2.0 lands them on the 100-scale
        potential_factor = DEVELOPMENT_PROFILES[potential]["ceiling_modifier"]
        adjusted_value = int(value * 2.0 * potential_factor)
        # Ensure it stays within valid bounds
        adjusted_value = max(GameBalance.MIN_ATTRIBUTE, min(GameBalance.MAX_ATTRIBUTE, adjusted_value))
        # Set the attribute
        setattr(player, attr, adjusted_value)

    # Positioning split (2026-09-28, per Muck): skaters roll
    # offensive/defensive positioning from their archetype on the same
    # 20-scale x2.0 x potential_factor conversion. Goalies keep the single
    # `positioning` (crease). ~1.5% unicorns come out elite at both ends.
    if position != PlayerPosition.GOALIE:
        _split = _ARCHETYPE_POSITIONING_SPLIT.get(archetype_name)
        if _split:
            _pf = DEVELOPMENT_PROFILES[potential]["ceiling_modifier"]
            (_olo, _ohi), (_dlo, _dhi) = _split
            _off20, _def20 = mesh_system.roll_positioning_split(_olo, _ohi, _dlo, _dhi)
            player.offensive_positioning = max(
                GameBalance.MIN_ATTRIBUTE,
                min(GameBalance.MAX_ATTRIBUTE, int(_off20 * 2.0 * _pf)))
            player.defensive_positioning = max(
                GameBalance.MIN_ATTRIBUTE,
                min(GameBalance.MAX_ATTRIBUTE, int(_def20 * 2.0 * _pf)))
    
    # Apply archetype-specific tendencies if available
    for tendency, (min_val, max_val) in archetype_data.get("tendency", {}).items():
        setattr(player, tendency, random.randint(min_val, max_val))
    
    # --- Goalie variance model (Task E) ---
    # Goalies develop late and unpredictably: depress CURRENT ability relative
    # to the displayed potential grade (GOALIE_RAWNESS_RANGE multiplier on
    # goalie-specific attributes) while the grade-driven archetype boosts
    # (ceilings) are untouched. Result: a WIDER current-vs-potential gap for
    # goalies than skaters -- lower floors, similar ceilings.
    if position == PlayerPosition.GOALIE:
        _raw = random.uniform(*GOALIE_RAWNESS_RANGE)
        for _attr in ('goaltending', 'reflexes', 'positioning', 'rebound_control',
                      'puck_handling', 'glove_hand', 'stick_side', 'breakaway_skill',
                      'confidence', 'focus', 'composure'):
            _cur = getattr(player, _attr, None)
            if isinstance(_cur, (int, float)):
                setattr(player, _attr, max(GameBalance.MIN_ATTRIBUTE,
                                          int(_cur * _raw)))

    # Personality blend: every prospect gets a real mix of drama, temper,
    # and difficulty -- identity dealt once, here, at generation. The class
    # tilt (if any) gives this draft class its own character.
    try:
        player.archetype = archetype_name
    except Exception:
        pass
    try:
        import reputation_system as _rs
        _rs.deal_generation_blend(player, tilt=personality_tilt)
    except Exception:
        pass

    # Calculate draft ranking for later sorting
    player.draft_ranking = calculate_draft_ranking(player)

    # Draft hype/pressure defaults (generate_draft_class refines these after
    # rank-sorting so hype tracks draft stock). hidden_gem flags the
    # guaranteed late-round goalie steals; the coordinator's realism pass
    # may set it for skaters too.
    player.draft_hype = 50
    player.draft_pressure = 30 if age == 18 else 15
    player.hidden_gem = False

    return player

def generate_draft_class(num_prospects: int = 224, quality: str = "Normal",
                        draft_year: Optional[int] = None,
                        reentries: Optional[List[Player]] = None) -> list[Player]:
    """
    Generates a list of draft-eligible players for the draft, with a realistic
    distribution of talent.

    quality: "Weak" | "Normal" | "Strong" | "Generational" — shifts the
        potential distribution up or down. "Normal" matches real NHL draft
        hit rates (~1 generational talent, ~11 elite/top-line per 224).
    draft_year: the June draft this class is for. Defaults to the next June
        draft derived from today's date (next year if month >= 7, else this
        year). Every generated prospect's birthdate is drawn from the
        is_draft_eligible() window for that year.
    reentries: already-created Player objects (CHL overagers re-entering the
        draft, supplied by another worker via league.draft_reentries).
        Inserted FIRST, counted toward num_prospects, keeping their existing
        age/birthdate/nationality; any re-entry failing is_draft_eligible()
        for draft_year is skipped.
    """
    if draft_year is None:
        draft_year = _default_draft_year()
    distribution = DRAFT_QUALITY_DISTRIBUTIONS.get(quality, POTENTIAL_DISTRIBUTION)
    prospects: list[Player] = []

    # Class character: most drafts are neutral, but some classes come in
    # with a temperament of their own -- a fiery class, a circus class, a
    # sulky one, a professional one. The league's personality shifts as the
    # seasons turn.
    try:
        import reputation_system as _rs_tilt
        _class_tilt = _rs_tilt.roll_class_tilt()
    except Exception:
        _class_tilt = None

    # Ensure we have a minimum number of players at each position.
    # Goalies keep a floor of 18 (real drafts take ~20-25 of 224); the 0.10
    # share lands ~22 typically, the floor guards the low tail.
    position_counts = {pos: 0 for pos in PlayerPosition}
    min_per_position = {pos: 20 for pos in PlayerPosition}
    min_per_position[PlayerPosition.GOALIE] = 18

    # Re-entries go first and count toward the total and position floors.
    # Re-entries are real pre-existing players, so a name clash between two
    # of them is normalized deterministically (first keeps the name, later
    # ones take Jr./II/III/IV, then a numeric disambiguator) -- never by
    # random re-roll, which would rewrite a real player's identity.
    _reentry_names = set()
    _REENTRY_SUFFIXES = ("Jr.", "II", "III", "IV")
    for _rp in (reentries or []):
        try:
            _ok = is_draft_eligible(getattr(_rp, "birth_date", ""),
                                    getattr(_rp, "nationality", ""),
                                    draft_year)
        except Exception:
            _ok = False
        if not _ok:
            continue
        _rkey = (getattr(_rp, "first_name", ""),
                 getattr(_rp, "last_name", ""))
        if _rkey in _reentry_names:
            _bfn, _bln = _rkey
            for _sfx in _REENTRY_SUFFIXES:
                if (_bfn, f"{_bln} {_sfx}") not in _reentry_names:
                    _rp.last_name = f"{_bln} {_sfx}"
                    _rkey = (_bfn, _rp.last_name)
                    break
            else:
                _i = 2
                while (_bfn, f"{_bln} {_i}") in _reentry_names:
                    _i += 1
                _rp.last_name = f"{_bln} {_i}"
                _rkey = (_bfn, _rp.last_name)
        _reentry_names.add(_rkey)
        _rp.draft_year = draft_year
        if not getattr(_rp, "draft_ranking", 0):
            _rp.draft_ranking = calculate_draft_ranking(_rp)
        if not getattr(_rp, "junior_league", ""):
            _rp.junior_league = _assign_junior_league(
                getattr(_rp, "nationality", "Canada"))
        if not hasattr(_rp, "hidden_gem"):
            _rp.hidden_gem = False
        # Legacy re-entries never got a personality dealt (draft prospects
        # only started receiving one now): deal once, here. No blend
        # reshape -- their attributes are already set, so the deal reads
        # them as-is. Identity dealt once, never re-dealt.
        try:
            import reputation_system as _rs_re
            _rs_re.generate_personality(_rp)
        except Exception:
            pass
        position_counts[_rp.primary_position] = \
            position_counts.get(_rp.primary_position, 0) + 1
        prospects.append(_rp)

    # Ensure we have a minimum number of players at each potential tier
    potential_counts = {pot: 0 for pot in distribution.keys()}

    # Name dedup: no two prospects in one class share a full name.
    # Repetitive draft classes break the fiction that these are 224
    # distinct kids. Seeded with the re-entries so a generated kid can't
    # collide with them either.
    _used_names = {(getattr(_p, "first_name", ""), getattr(_p, "last_name", ""))
                   for _p in prospects}
    _SUFFIXES = ("Jr.", "II", "III", "IV")

    def _unique_name(prospect):
        """Ensure prospect.first/last_name is unique in this class.

        Bounded re-rolls first (keeps the name pool natural); the
        deterministic suffix fallback guarantees termination even if the
        pool is pathological -- no collision is ever accepted.
        """
        _key = (prospect.first_name, prospect.last_name)
        for _ in range(8):
            if _key not in _used_names:
                break
            _fn, _ln = get_random_name(prospect.nationality)
            prospect.first_name, prospect.last_name = _fn, _ln
            _key = (_fn, _ln)
        if _key in _used_names:
            _base_fn, _base_ln = _key
            for _sfx in _SUFFIXES:
                _cand = (_base_fn, f"{_base_ln} {_sfx}")
                if _cand not in _used_names:
                    prospect.first_name, prospect.last_name = _cand
                    _key = _cand
                    break
            else:
                # Absolute fallback: numeric disambiguator. Unreachable in
                # practice (4 suffixes x re-rolls), but termination is
                # guaranteed, not hoped for.
                _i = 2
                while (_base_fn, f"{_base_ln} {_i}") in _used_names:
                    _i += 1
                prospect.first_name = _base_fn
                prospect.last_name = f"{_base_ln} {_i}"
                _key = (prospect.first_name, prospect.last_name)
        _used_names.add(_key)

    # Generate enough prospects to meet the requested total
    _SKATER_POSITIONS = [p for p in PlayerPosition
                         if p != PlayerPosition.GOALIE]
    while len(prospects) < num_prospects:
        # Determine if we need to force a specific position
        forced_position = None
        for pos, count in position_counts.items():
            if count < min_per_position[pos]:
                forced_position = pos
                break
        # Soft cap: real drafts take ~20-25 goalies of 224. Once 25 are in,
        # draw skaters instead (the floor above guarantees the low end).
        if (forced_position is None
                and position_counts.get(PlayerPosition.GOALIE, 0) >= 25):
            forced_position = random.choice(_SKATER_POSITIONS)

        # Age mix: mostly 18, some 19, a few 20, rare 21-24 Europeans.
        # (21+ is only legal for non-NA nationalities, so force one.)
        _age = _roll_prospect_age()
        _nat = _random_european_nationality() if _age >= 21 else None

        # Generate the prospect
        prospect = create_prospect(age=_age,
                                   position=forced_position,
                                   nationality=_nat,
                                   potential_distribution=distribution,
                                   draft_year=draft_year,
                                   personality_tilt=_class_tilt)

        # Defensive: never emit an ineligible prospect. (Birthdates are drawn
        # from the eligible window, so this should never trigger.)
        if not is_draft_eligible(prospect.birth_date, prospect.nationality,
                                 draft_year):
            continue

        # Name dedup: a full-name collision gets a re-roll (bounded), then
        # a deterministic suffix -- every class has 224 distinct names.
        _unique_name(prospect)

        # Update our counters
        position_counts[prospect.primary_position] += 1
        potential_counts[prospect.potential_grade] += 1

        # Add to our list
        prospects.append(prospect)

    # Sort prospects by draft ranking for convenience
    prospects.sort(key=lambda p: p.draft_ranking, reverse=True)

    # Draft hype (0-100) tracks draft stock: ~100 at #1, decaying down the
    # board. Draft pressure (0-100) runs hottest for hyped 18-year-olds.
    for _i, _p in enumerate(prospects):
        _p.draft_hype = max(2, min(100, int(100 * math.exp(-_i / 45.0)
                                             + random.uniform(-4, 4))))
        _press = _p.draft_hype * 0.6
        if _p.age == 18:
            _press += random.uniform(15, 30)
        elif _p.age == 19:
            _press += random.uniform(4, 10)
        _p.draft_pressure = max(0, min(100, int(_press)))

    # Hidden gems: a few later picks secretly carry a higher TRUE ceiling
    # than their displayed grade (the Zetterberg/Datsyuk/Kucherov seeds).
    # Scouting -- or loud farm production -- reveals them.
    # Goalies get fatter tails here (Task E): a pre-roll with higher bust AND
    # higher boom probability than the flat gem table skaters use.
    #
    # Ordering guard: create_prospect -> deal_generation_blend ->
    # ensure_reputation_fields backfills true_potential_grade = displayed
    # (an old-save backfill that also fires for fresh prospects). That
    # truthy value trips seed_true_potential's idempotency guard, which
    # would silently skip the whole gem table AND the draft_round stamp.
    # Clear it here so truth is dealt exactly once, below.
    try:
        import prospect_development as _pd
        _per_round = 32
        _ladder = _grade_ladder()
        for _i, _p in enumerate(prospects):
            _p.true_potential_grade = ""
            # Stamp the round unconditionally here: the goalie pre-roll below
            # sets a true grade before seed_true_potential runs, which would
            # otherwise leave pre-rolled goalies with draft_round == 0 via
            # the idempotency guard.
            _p.draft_round = _i // _per_round + 1
        for _i, _p in enumerate(prospects):
            if (_p.primary_position == PlayerPosition.GOALIE
                    and not getattr(_p, "true_potential_grade", "")):
                _r = random.random()
                _idx = _grade_ladder_index(_p.potential_grade)
                if _r < GOALIE_GEM_BOOM_PROB:
                    _p.true_potential_grade = _ladder[
                        min(_idx + random.choice([1, 2]), len(_ladder) - 1)]
                elif _r < GOALIE_GEM_BOOM_PROB + GOALIE_GEM_BUST_PROB:
                    _p.true_potential_grade = _ladder[max(_idx - 1, 0)]
            _pd.seed_true_potential(_p, draft_round=_i // _per_round + 1)
    except Exception:
        pass

    # Guarantee 1-2 hidden-gem goalies per class (Task E): drawn from round-3+
    # goalies, true grade bumped up to +2 (capped per grade, mirroring
    # prospect_development's bump caps), flagged via hidden_gem so late-round
    # goalie steals actually occur. Seeded RNG (global random) keeps this
    # deterministic-ish under a pinned seed.
    try:
        _ladder = _grade_ladder()
        _candidates = [p for _i, p in enumerate(prospects)
                       if p.primary_position == PlayerPosition.GOALIE
                       and _i >= 64
                       and not getattr(p, "hidden_gem", False)]
        _n_gems = random.randint(1, 2)
        for _g in random.sample(_candidates, min(_n_gems, len(_candidates))):
            _idx = _grade_ladder_index(_g.potential_grade)
            _cap = _GEM_BUMP_CAP.get((_g.potential_grade or "C").strip(), 1)
            _bump = min(2, _cap)
            _g.true_potential_grade = _ladder[min(_idx + _bump, len(_ladder) - 1)]
            _g.hidden_gem = True
    except Exception:
        pass

    # Hidden ELITE (the Datsyuk/Zetterberg/Kucherov case): a tiny fraction of
    # round-4+ prospects carry a genuinely ELITE true ceiling (A-/A) behind a
    # mid/late-round displayed grade. seed_true_potential's bump caps (+1/+2
    # with per-grade maxima) can never reach elite from a "C+" display, so
    # this separate rare roll exists. Displayed grade, hype, and draft slot
    # are untouched -- scouts see a mid-rounder; reality holds a star.
    # Rate: 0.5% of rounds 4-7 (~128 prospects) ~= 0.6/class. Most never get
    # identified or developed; realized round-4+ stars stay ~0-2/decade
    # league-wide. No schedule -- pure probability, some decades get none.
    # (Additive: only sets true_potential_grade, which prospect_development
    # already consumes as the real ceiling. No development logic touched.)
    try:
        _n_elite_hidden = 0
        for _i, _p in enumerate(prospects):
            if _i < 96:  # rounds 1-3: no hidden elites, only the gem table
                continue
            if getattr(_p, "generational", False):
                continue
            if random.random() < 0.005:
                _p.true_potential_grade = "A" if random.random() < 0.25 else "A-"
                _n_elite_hidden += 1
    except Exception:
        pass

    # PERCEIVED-generational flag (the obvious McDavid everyone sees coming):
    # true ceiling generational AND perceived #1. Probabilistic, never
    # scheduled: the roll below is calibrated so the UNCONDITIONAL rate is
    # ~14% (~once every 5-8 years). Only ~28% of classes have an A+
    # consensus #1 at all, so the roll fires ~half the time such a class
    # appears (0.50 x 0.28 ~= 0.14). A class whose top prospect isn't A+
    # simply has no generational that year; some decades get two, some none.
    # Only a flagged prospect gets the #1 lock on all 32 team boards and the
    # wall-to-wall headline treatment. Everyone else -- even elite A+ names --
    # is rankable 1st..15th by any team's scouts (awareness floor, order
    # freedom).
    try:
        for _p in prospects:
            _p.generational = False
        if (prospects and random.random() < 0.50
                and (prospects[0].potential_grade or "").strip() == "A+"):
            prospects[0].generational = True
            prospects[0].draft_hype = 100
    except Exception:
        pass

    print(f"Generated a new draft class with {len(prospects)} prospects (quality: {quality}, draft year: {draft_year}).")
    print(f"Potential distribution: {potential_counts}")

    # Prospect reputation + pre-draft junior stories: a light, one-pass
    # seeding (perceived potential only -- never hidden truth). Guarded so
    # a data bug here can never break class generation.
    try:
        import prospect_accolades as _pa
        # Isolated RNG: the global stream must stay exactly as it was
        # before this hook (downstream board/story code is seed-sensitive).
        _pa_stats = _pa.seed_draft_class(prospects, draft_year,
                                         rng=random.Random())
        print(f"Prospect accolades: {int(_pa_stats.get('seeded', 0))} repped, "
              f"{int(_pa_stats.get('storied', 0))} with junior stories.")
    except Exception:
        pass

    return prospects

