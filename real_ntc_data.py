# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Real-world NHL no-trade / no-movement clause data for 2026-27.

Every entry is a (player_name, team_name, clause, list_size, approved_list)
tuple:

- clause: "NMC" (full no-movement), "NTC" (full no-trade), "M-NTC"
  (modified no-trade -- the player holds a list).
- list_size: for M-NTC, how many teams are on the player's list.
- approved_list: True when the list is an *approved* trade list (the player
  may only go to those teams) instead of a no-trade list (he may go
  anywhere except those teams). Real-life lists are private, so the game
  only knows the size, not the teams.

Research: 2026-09-28. Primary source: Pro Hockey Rumors "Players With
Trade Protection In 2025-26" (July 2025, via PuckPedia), cross-checked
against PuckPedia player pages and the December 2025 PHR veto-trade
update. 2026-27 adjustments where confirmed (Chris Kreider's September
2026 Montreal deal carries a full NTC).

Scope notes:
- These are OPENING-DAY 2026-27 figures. A few clauses change shape
  mid-season in real life (e.g. Klingberg/Skinner NTCs become M-NTCs in
  January); the game seeds the opening-night status.
- The seeder only applies a clause when the player is actually on the
  listed team in the new game, so real-life 2026 moves never create stale
  clauses.
- Carey Price (listed on some 2025-26 sheets) is excluded -- LTIR/retired.
"""

# player, team, clause, list size, approved-list?
REAL_CLAUSES_2026_27 = [
    # Anaheim Ducks (Kreider -> Montreal, Sept 2026)
    ("Mikael Granlund", "Anaheim Ducks", "NTC", 0, False),
    ("Radko Gudas", "Anaheim Ducks", "M-NTC", 10, False),
    ("Alex Killorn", "Anaheim Ducks", "M-NTC", 15, False),
    ("Troy Terry", "Anaheim Ducks", "M-NTC", 10, False),
    ("Jacob Trouba", "Anaheim Ducks", "M-NTC", 12, False),
    ("Frank Vatrano", "Anaheim Ducks", "M-NTC", 7, False),
    # Boston Bruins
    ("Viktor Arvidsson", "Boston Bruins", "NMC", 0, False),
    ("Elias Lindholm", "Boston Bruins", "NMC", 0, False),
    ("Hampus Lindholm", "Boston Bruins", "NMC", 0, False),
    ("Charlie McAvoy", "Boston Bruins", "NMC", 0, False),
    ("David Pastrnak", "Boston Bruins", "NMC", 0, False),
    ("Tanner Jeannot", "Boston Bruins", "NTC", 0, False),
    ("Nikita Zadorov", "Boston Bruins", "NTC", 0, False),
    ("Henri Jokiharju", "Boston Bruins", "M-NTC", 8, False),
    ("Joonas Korpisalo", "Boston Bruins", "M-NTC", 10, False),
    ("Pavel Zacha", "Boston Bruins", "M-NTC", 8, False),
    # Buffalo Sabres
    ("Rasmus Dahlin", "Buffalo Sabres", "NMC", 0, False),
    ("Jordan Greenway", "Buffalo Sabres", "M-NTC", 5, False),
    ("Tage Thompson", "Buffalo Sabres", "M-NTC", 5, False),
    ("Alex Tuch", "Buffalo Sabres", "M-NTC", 5, False),
    ("Jason Zucker", "Buffalo Sabres", "M-NTC", 5, False),
    # Calgary Flames
    ("Mikael Backlund", "Calgary Flames", "NMC", 15, False),
    ("Jonathan Huberdeau", "Calgary Flames", "NMC", 0, False),
    ("Nazem Kadri", "Calgary Flames", "NMC", 0, False),
    ("MacKenzie Weegar", "Calgary Flames", "NTC", 0, False),
    ("Rasmus Andersson", "Calgary Flames", "M-NTC", 6, False),
    ("Blake Coleman", "Calgary Flames", "M-NTC", 10, True),
    ("Yegor Sharangovich", "Calgary Flames", "M-NTC", 10, False),
    # Carolina Hurricanes
    ("Sebastian Aho", "Carolina Hurricanes", "NMC", 0, False),
    ("Frederik Andersen", "Carolina Hurricanes", "NMC", 20, False),
    ("William Carrier", "Carolina Hurricanes", "NMC", 0, False),
    ("Jalen Chatfield", "Carolina Hurricanes", "NMC", 0, False),
    ("Nikolaj Ehlers", "Carolina Hurricanes", "NMC", 0, False),
    ("Taylor Hall", "Carolina Hurricanes", "NMC", 0, False),
    ("Jaccob Slavin", "Carolina Hurricanes", "NMC", 0, False),
    ("Jordan Staal", "Carolina Hurricanes", "NMC", 0, False),
    ("Shayne Gostisbehere", "Carolina Hurricanes", "M-NTC", 15, False),
    ("Jordan Martinook", "Carolina Hurricanes", "M-NTC", 10, False),
    ("Eric Robinson", "Carolina Hurricanes", "M-NTC", 8, False),
    ("Andrei Svechnikov", "Carolina Hurricanes", "M-NTC", 10, True),
    ("Sean Walker", "Carolina Hurricanes", "M-NTC", 15, False),
    # Chicago Blackhawks
    ("Tyler Bertuzzi", "Chicago Blackhawks", "M-NTC", 10, False),
    ("Andre Burakovsky", "Chicago Blackhawks", "M-NTC", 10, False),
    ("Ryan Donato", "Chicago Blackhawks", "M-NTC", 10, False),
    ("Ilya Mikheyev", "Chicago Blackhawks", "M-NTC", 12, False),
    ("Connor Murphy", "Chicago Blackhawks", "M-NTC", 10, False),
    ("Teuvo Teravainen", "Chicago Blackhawks", "M-NTC", 8, False),
    # Colorado Avalanche
    ("Gabriel Landeskog", "Colorado Avalanche", "NMC", 12, False),
    ("Nathan MacKinnon", "Colorado Avalanche", "NMC", 0, False),
    ("Devon Toews", "Colorado Avalanche", "NMC", 0, False),
    ("Brock Nelson", "Colorado Avalanche", "NTC", 0, False),
    ("Mackenzie Blackwood", "Colorado Avalanche", "M-NTC", 6, False),
    ("Ross Colton", "Colorado Avalanche", "M-NTC", 12, False),
    ("Samuel Girard", "Colorado Avalanche", "M-NTC", 9, False),
    ("Artturi Lehkonen", "Colorado Avalanche", "M-NTC", 12, False),
    ("Josh Manson", "Colorado Avalanche", "M-NTC", 12, False),
    ("Valeri Nichushkin", "Colorado Avalanche", "M-NTC", 12, False),
    ("Logan O'Connor", "Colorado Avalanche", "M-NTC", 6, False),
    # Columbus Blue Jackets
    ("Charlie Coyle", "Columbus Blue Jackets", "NMC", 3, False),
    ("Sean Monahan", "Columbus Blue Jackets", "NMC", 0, False),
    ("Ivan Provorov", "Columbus Blue Jackets", "NMC", 15, False),
    ("Zach Werenski", "Columbus Blue Jackets", "NMC", 0, False),
    ("Damon Severson", "Columbus Blue Jackets", "NTC", 0, False),
    ("Erik Gudbranson", "Columbus Blue Jackets", "M-NTC", 10, False),
    ("Boone Jenner", "Columbus Blue Jackets", "M-NTC", 8, False),
    ("Elvis Merzlikins", "Columbus Blue Jackets", "M-NTC", 10, False),
    ("Mathieu Olivier", "Columbus Blue Jackets", "M-NTC", 10, False),
    ("Miles Wood", "Columbus Blue Jackets", "M-NTC", 6, False),
    # Dallas Stars
    ("Jamie Benn", "Dallas Stars", "NMC", 0, False),
    ("Matt Duchene", "Dallas Stars", "NMC", 0, False),
    ("Miro Heiskanen", "Dallas Stars", "NMC", 0, False),
    ("Roope Hintz", "Dallas Stars", "NMC", 0, False),
    ("Mikko Rantanen", "Dallas Stars", "NMC", 0, False),
    ("Tyler Seguin", "Dallas Stars", "NMC", 0, False),
    ("Esa Lindell", "Dallas Stars", "NTC", 0, False),
    # Detroit Red Wings
    ("Patrick Kane", "Detroit Red Wings", "NTC", 0, False),
    ("Dylan Larkin", "Detroit Red Wings", "NTC", 0, False),
    ("Ben Chiarot", "Detroit Red Wings", "M-NTC", 10, False),
    ("J.T. Compher", "Detroit Red Wings", "M-NTC", 10, False),
    ("Andrew Copp", "Detroit Red Wings", "M-NTC", 10, False),
    ("Alex DeBrincat", "Detroit Red Wings", "M-NTC", 16, False),
    ("John Gibson", "Detroit Red Wings", "M-NTC", 10, False),
    ("Justin Holl", "Detroit Red Wings", "M-NTC", 10, False),
    # Edmonton Oilers
    ("Leon Draisaitl", "Edmonton Oilers", "NMC", 0, False),
    ("Trent Frederic", "Edmonton Oilers", "NMC", 0, False),
    ("Adam Henrique", "Edmonton Oilers", "NMC", 0, False),
    ("Zach Hyman", "Edmonton Oilers", "NMC", 10, False),
    ("Connor McDavid", "Edmonton Oilers", "NMC", 0, False),
    ("Ryan Nugent-Hopkins", "Edmonton Oilers", "NMC", 0, False),
    ("Darnell Nurse", "Edmonton Oilers", "NMC", 0, False),
    ("Jake Walman", "Edmonton Oilers", "NMC", 0, False),
    ("Andrew Mangiapane", "Edmonton Oilers", "NTC", 0, False),
    ("Mattias Janmark", "Edmonton Oilers", "M-NTC", 10, False),
    ("Jack Roslovic", "Edmonton Oilers", "M-NTC", 4, True),
    # Florida Panthers
    ("Aleksander Barkov", "Florida Panthers", "NMC", 0, False),
    ("Sam Bennett", "Florida Panthers", "NMC", 0, False),
    ("Aaron Ekblad", "Florida Panthers", "NMC", 0, False),
    ("Gustav Forsling", "Florida Panthers", "NMC", 0, False),
    ("Seth Jones", "Florida Panthers", "NMC", 0, False),
    ("Brad Marchand", "Florida Panthers", "NMC", 0, False),
    ("Sam Reinhart", "Florida Panthers", "NMC", 16, False),
    ("Matthew Tkachuk", "Florida Panthers", "NMC", 0, False),
    ("Carter Verhaeghe", "Florida Panthers", "NMC", 0, False),
    ("Sergei Bobrovsky", "Florida Panthers", "M-NTC", 16, False),
    # Los Angeles Kings
    ("Kevin Fiala", "Los Angeles Kings", "NMC", 0, False),
    ("Anze Kopitar", "Los Angeles Kings", "NMC", 0, False),
    ("Cody Ceci", "Los Angeles Kings", "M-NTC", 10, False),
    ("Phillip Danault", "Los Angeles Kings", "M-NTC", 10, False),
    ("Drew Doughty", "Los Angeles Kings", "M-NTC", 7, True),
    ("Brian Dumoulin", "Los Angeles Kings", "M-NTC", 10, False),
    ("Joel Edmundson", "Los Angeles Kings", "M-NTC", 10, False),
    ("Warren Foegele", "Los Angeles Kings", "M-NTC", 5, False),
    ("Adrian Kempe", "Los Angeles Kings", "M-NTC", 10, False),
    ("Darcy Kuemper", "Los Angeles Kings", "M-NTC", 10, False),
    # Minnesota Wild
    ("Joel Eriksson Ek", "Minnesota Wild", "NMC", 10, False),
    ("Marcus Foligno", "Minnesota Wild", "NMC", 0, False),
    ("Kirill Kaprizov", "Minnesota Wild", "NMC", 0, False),
    ("Jacob Middleton", "Minnesota Wild", "NMC", 0, False),
    ("Mats Zuccarello", "Minnesota Wild", "NMC", 0, False),
    ("Filip Gustavsson", "Minnesota Wild", "M-NTC", 5, False),
    ("Ryan Hartman", "Minnesota Wild", "M-NTC", 15, False),
    ("Jared Spurgeon", "Minnesota Wild", "M-NTC", 10, False),
    ("Vladimir Tarasenko", "Minnesota Wild", "M-NTC", 8, True),
    # Montreal Canadiens (Kreider signed Sept 2026 with full NTC)
    ("Brendan Gallagher", "Montreal Canadiens", "NMC", 6, False),
    ("Chris Kreider", "Montreal Canadiens", "NTC", 0, False),
    ("Josh Anderson", "Montreal Canadiens", "M-NTC", 5, False),
    ("Patrik Laine", "Montreal Canadiens", "M-NTC", 10, False),
    ("Mike Matheson", "Montreal Canadiens", "M-NTC", 8, False),
    # Nashville Predators
    ("Filip Forsberg", "Nashville Predators", "NMC", 0, False),
    ("Roman Josi", "Nashville Predators", "NMC", 0, False),
    ("Jonathan Marchessault", "Nashville Predators", "NMC", 0, False),
    ("Juuse Saros", "Nashville Predators", "NMC", 0, False),
    ("Brady Skjei", "Nashville Predators", "NMC", 15, False),
    ("Steven Stamkos", "Nashville Predators", "NMC", 0, False),
    ("Erik Haula", "Nashville Predators", "M-NTC", 6, False),
    # New Jersey Devils
    ("Jesper Bratt", "New Jersey Devils", "NMC", 0, False),
    ("Dougie Hamilton", "New Jersey Devils", "NMC", 10, True),
    ("Jacob Markstrom", "New Jersey Devils", "NMC", 0, False),
    ("Timo Meier", "New Jersey Devils", "NMC", 0, False),
    ("Ondrej Palat", "New Jersey Devils", "NMC", 10, True),
    ("Jake Allen", "New Jersey Devils", "NTC", 0, False),
    ("Connor Brown", "New Jersey Devils", "NTC", 0, False),
    ("Evgenii Dadonov", "New Jersey Devils", "NTC", 10, False),
    ("Brenden Dillon", "New Jersey Devils", "NTC", 0, False),
    ("Johnathan Kovacevic", "New Jersey Devils", "NTC", 0, False),
    ("Brett Pesce", "New Jersey Devils", "NTC", 0, False),
    ("Nico Hischier", "New Jersey Devils", "M-NTC", 10, False),
    ("Stefan Noesen", "New Jersey Devils", "M-NTC", 10, False),
    ("Jonas Siegenthaler", "New Jersey Devils", "M-NTC", 10, False),
    ("Dan Vladar", "New Jersey Devils", "M-NTC", 8, False),
    # New York Islanders
    ("Ilya Sorokin", "New York Islanders", "NMC", 0, False),
    ("Anthony Duclair", "New York Islanders", "NTC", 0, False),
    ("Bo Horvat", "New York Islanders", "NTC", 0, False),
    ("Scott Mayfield", "New York Islanders", "NTC", 0, False),
    ("Kyle Palmieri", "New York Islanders", "NTC", 0, False),
    ("Ryan Pulock", "New York Islanders", "NTC", 0, False),
    ("Mathew Barzal", "New York Islanders", "M-NTC", 22, False),
    ("Jonathan Drouin", "New York Islanders", "M-NTC", 16, False),
    ("Pierre Engvall", "New York Islanders", "M-NTC", 16, False),
    ("Anders Lee", "New York Islanders", "M-NTC", 15, False),
    ("Jean-Gabriel Pageau", "New York Islanders", "M-NTC", 16, False),
    ("Adam Pelech", "New York Islanders", "M-NTC", 16, False),
    ("Semyon Varlamov", "New York Islanders", "M-NTC", 16, False),
    # New York Rangers
    ("Adam Fox", "New York Rangers", "NMC", 0, False),
    ("Vladislav Gavrikov", "New York Rangers", "NMC", 0, False),
    ("J.T. Miller", "New York Rangers", "NMC", 0, False),
    ("Artemi Panarin", "New York Rangers", "NMC", 0, False),
    ("Igor Shesterkin", "New York Rangers", "NMC", 0, False),
    ("Mika Zibanejad", "New York Rangers", "NMC", 21, False),
    ("Will Borgen", "New York Rangers", "NTC", 0, False),
    ("Jonathan Quick", "New York Rangers", "M-NTC", 20, False),
    ("Carson Soucy", "New York Rangers", "M-NTC", 12, False),
    ("Vincent Trocheck", "New York Rangers", "M-NTC", 12, False),
    # Ottawa Senators
    ("Claude Giroux", "Ottawa Senators", "NMC", 0, False),
    ("Brady Tkachuk", "Ottawa Senators", "NMC", 0, False),
    ("Linus Ullmark", "Ottawa Senators", "NMC", 0, False),
    ("Thomas Chabot", "Ottawa Senators", "M-NTC", 10, False),
    ("Lars Eller", "Ottawa Senators", "M-NTC", 14, True),
    ("David Perron", "Ottawa Senators", "M-NTC", 15, False),
    ("Artem Zub", "Ottawa Senators", "M-NTC", 10, False),
    # Philadelphia Flyers
    ("Sean Couturier", "Philadelphia Flyers", "NMC", 0, False),
    ("Travis Konecny", "Philadelphia Flyers", "NMC", 0, False),
    ("Travis Sanheim", "Philadelphia Flyers", "NTC", 0, False),
    ("Nick Seeler", "Philadelphia Flyers", "NTC", 0, False),
    ("Dan Vladar", "Philadelphia Flyers", "M-NTC", 8, False),
    # Pittsburgh Penguins
    ("Sidney Crosby", "Pittsburgh Penguins", "NMC", 0, False),
    ("Erik Karlsson", "Pittsburgh Penguins", "NMC", 0, False),
    ("Kris Letang", "Pittsburgh Penguins", "NMC", 0, False),
    ("Evgeni Malkin", "Pittsburgh Penguins", "NMC", 0, False),
    ("Noel Acciari", "Pittsburgh Penguins", "M-NTC", 8, False),
    ("Ryan Graves", "Pittsburgh Penguins", "M-NTC", 12, False),
    ("Kevin Hayes", "Pittsburgh Penguins", "M-NTC", 12, False),
    ("Danton Heinen", "Pittsburgh Penguins", "M-NTC", 12, False),
    ("Tristan Jarry", "Pittsburgh Penguins", "M-NTC", 12, False),
    ("Rickard Rakell", "Pittsburgh Penguins", "M-NTC", 8, False),
    # San Jose Sharks
    ("John Klingberg", "San Jose Sharks", "NTC", 14, False),
    ("Dmitry Orlov", "San Jose Sharks", "NTC", 0, False),
    ("Jeff Skinner", "San Jose Sharks", "NTC", 8, True),
    ("Tyler Toffoli", "San Jose Sharks", "NTC", 0, False),
    ("Logan Couture", "San Jose Sharks", "M-NTC", 3, True),
    ("Barclay Goodrow", "San Jose Sharks", "M-NTC", 15, False),
    ("Alexander Wennberg", "San Jose Sharks", "M-NTC", 15, True),
    # Seattle Kraken
    ("Chandler Stephenson", "Seattle Kraken", "NMC", 0, False),
    ("Jordan Eberle", "Seattle Kraken", "NTC", 0, False),
    ("Adam Larsson", "Seattle Kraken", "NTC", 0, False),
    ("Brandon Montour", "Seattle Kraken", "NTC", 0, False),
    ("Joey Daccord", "Seattle Kraken", "M-NTC", 12, False),
    ("Vince Dunn", "Seattle Kraken", "M-NTC", 16, False),
    ("Frederick Gaudreau", "Seattle Kraken", "M-NTC", 15, False),
    ("Philipp Grubauer", "Seattle Kraken", "M-NTC", 10, False),
    ("Ryan Lindgren", "Seattle Kraken", "M-NTC", 6, False),
    ("Mason Marchment", "Seattle Kraken", "M-NTC", 10, False),
    ("Jared McCann", "Seattle Kraken", "M-NTC", 10, False),
    ("Jamie Oleksiak", "Seattle Kraken", "M-NTC", 16, False),
    ("Jaden Schwartz", "Seattle Kraken", "M-NTC", 16, False),
    # St. Louis Blues
    ("Pavel Buchnevich", "St. Louis Blues", "NTC", 0, False),
    ("Jordan Kyrou", "St. Louis Blues", "NTC", 0, False),
    ("Colton Parayko", "St. Louis Blues", "NTC", 0, False),
    ("Robert Thomas", "St. Louis Blues", "NTC", 0, False),
    ("Jordan Binnington", "St. Louis Blues", "M-NTC", 14, False),
    ("Justin Faulk", "St. Louis Blues", "M-NTC", 15, False),
    ("Cam Fowler", "St. Louis Blues", "M-NTC", 4, True),
    ("Torey Krug", "St. Louis Blues", "M-NTC", 15, False),
    ("Brayden Schenn", "St. Louis Blues", "M-NTC", 15, False),
    # Tampa Bay Lightning
    ("Jake Guentzel", "Tampa Bay Lightning", "NMC", 0, False),
    ("Victor Hedman", "Tampa Bay Lightning", "NMC", 0, False),
    ("Brayden Point", "Tampa Bay Lightning", "NMC", 0, False),
    ("Erik Cernak", "Tampa Bay Lightning", "NTC", 0, False),
    ("Anthony Cirelli", "Tampa Bay Lightning", "NTC", 0, False),
    ("Yanni Gourde", "Tampa Bay Lightning", "NTC", 0, False),
    ("Nick Paul", "Tampa Bay Lightning", "NTC", 0, False),
    ("Oliver Bjorkstrand", "Tampa Bay Lightning", "M-NTC", 10, False),
    ("Zemgus Girgensons", "Tampa Bay Lightning", "M-NTC", 16, True),
    ("Nikita Kucherov", "Tampa Bay Lightning", "M-NTC", 10, True),
    ("Ryan McDonagh", "Tampa Bay Lightning", "M-NTC", 12, False),
    ("Andrei Vasilevskiy", "Tampa Bay Lightning", "NMC", 10, True),
    # Toronto Maple Leafs
    ("Auston Matthews", "Toronto Maple Leafs", "NMC", 0, False),
    ("William Nylander", "Toronto Maple Leafs", "NMC", 0, False),
    ("Morgan Rielly", "Toronto Maple Leafs", "NMC", 0, False),
    ("Chris Tanev", "Toronto Maple Leafs", "NMC", 0, False),
    ("John Tavares", "Toronto Maple Leafs", "NMC", 0, False),
    ("Jake McCabe", "Toronto Maple Leafs", "NTC", 0, False),
    ("Brandon Carlo", "Toronto Maple Leafs", "M-NTC", 8, False),
    ("Max Domi", "Toronto Maple Leafs", "M-NTC", 13, False),
    ("Oliver Ekman-Larsson", "Toronto Maple Leafs", "M-NTC", 16, False),
    ("Calle Jarnkrok", "Toronto Maple Leafs", "M-NTC", 10, False),
    ("David Kampf", "Toronto Maple Leafs", "M-NTC", 10, False),
    ("Anthony Stolarz", "Toronto Maple Leafs", "M-NTC", 8, False),
    # Utah Mammoth
    ("Clayton Keller", "Utah Mammoth", "NTC", 0, False),
    ("Mikhail Sergachev", "Utah Mammoth", "NTC", 0, False),
    ("John Marino", "Utah Mammoth", "M-NTC", 8, False),
    ("Olli Maatta", "Utah Mammoth", "M-NTC", 10, False),
    ("Nick Schmaltz", "Utah Mammoth", "M-NTC", 10, False),
    ("Nate Schmidt", "Utah Mammoth", "M-NTC", 10, False),
    ("Brandon Tanev", "Utah Mammoth", "M-NTC", 10, False),
    ("Karel Vejmelka", "Utah Mammoth", "M-NTC", 10, False),
    # Vancouver Canucks
    ("Brock Boeser", "Vancouver Canucks", "NMC", 0, False),
    ("Jake DeBrusk", "Vancouver Canucks", "NMC", 0, False),
    ("Filip Hronek", "Vancouver Canucks", "NMC", 0, False),
    ("Kevin Lankinen", "Vancouver Canucks", "NMC", 0, False),
    ("Tyler Myers", "Vancouver Canucks", "NMC", 0, False),
    ("Elias Pettersson", "Vancouver Canucks", "NMC", 0, False),
    ("Marcus Pettersson", "Vancouver Canucks", "NMC", 0, False),
    ("Teddy Blueger", "Vancouver Canucks", "M-NTC", 12, False),
    ("Dakota Joshua", "Vancouver Canucks", "M-NTC", 12, False),
    ("Evander Kane", "Vancouver Canucks", "M-NTC", 16, True),
    ("Drew O'Connor", "Vancouver Canucks", "M-NTC", 12, False),
    # Vegas Golden Knights
    ("Jack Eichel", "Vegas Golden Knights", "NMC", 0, False),
    ("Mitch Marner", "Vegas Golden Knights", "NMC", 0, False),
    ("Alex Pietrangelo", "Vegas Golden Knights", "NMC", 0, False),
    ("Mark Stone", "Vegas Golden Knights", "NMC", 0, False),
    ("Noah Hanifin", "Vegas Golden Knights", "NTC", 0, False),
    ("Brayden McNabb", "Vegas Golden Knights", "NTC", 0, False),
    ("Brandon Saad", "Vegas Golden Knights", "NTC", 0, False),
    ("Reilly Smith", "Vegas Golden Knights", "NTC", 0, False),
    ("Shea Theodore", "Vegas Golden Knights", "NTC", 0, False),
    ("Ivan Barbashev", "Vegas Golden Knights", "M-NTC", 8, False),
    ("Tomas Hertl", "Vegas Golden Knights", "M-NTC", 3, True),
    ("Adin Hill", "Vegas Golden Knights", "M-NTC", 10, False),
    ("William Karlsson", "Vegas Golden Knights", "M-NTC", 10, False),
    # Washington Capitals
    ("Jakob Chychrun", "Washington Capitals", "NMC", 0, False),
    ("Pierre-Luc Dubois", "Washington Capitals", "NMC", 0, False),
    ("Alex Ovechkin", "Washington Capitals", "NMC", 10, False),
    ("John Carlson", "Washington Capitals", "M-NTC", 10, False),
    ("Matt Roy", "Washington Capitals", "M-NTC", 15, False),
    ("Logan Thompson", "Washington Capitals", "M-NTC", 15, False),
    ("Tom Wilson", "Washington Capitals", "M-NTC", 14, False),
    # Winnipeg Jets
    ("Connor Hellebuyck", "Winnipeg Jets", "NMC", 0, False),
    ("Mark Scheifele", "Winnipeg Jets", "NMC", 0, False),
    ("Jonathan Toews", "Winnipeg Jets", "NMC", 0, False),
    ("Kyle Connor", "Winnipeg Jets", "M-NTC", 10, False),
    ("Dylan DeMelo", "Winnipeg Jets", "M-NTC", 10, False),
    ("Adam Lowry", "Winnipeg Jets", "M-NTC", 6, False),
    ("Josh Morrissey", "Winnipeg Jets", "M-NTC", 15, False),
    ("Neal Pionk", "Winnipeg Jets", "M-NTC", 15, False),
]

SEASON = 2026  # opening-day 2026-27 season


def _norm(name):
    return "".join(c.lower() for c in name if c.isalnum())


def seed_real_clauses(league):
    """Stamp real-life 2026-27 NTC/NMC/M-NTC clauses onto matching players.

    Only applies when the player is on the listed team in this league --
    real-life moves never create stale clauses. Returns the number of
    players stamped. Safe to call on any league; additive only.
    """
    try:
        teams = {t.team_name: t for t in getattr(league, "teams", [])}
    except Exception:
        return 0
    stamped = 0
    for name, team_name, clause, list_size, approved in REAL_CLAUSES_2026_27:
        team = teams.get(team_name)
        if team is None:
            continue
        roster = list(getattr(team, "roster", []) or [])
        roster += list(getattr(team, "ahl_roster", []) or [])
        roster += list(getattr(team, "prospects", []) or [])
        target = _norm(name)
        for p in roster:
            try:
                full = _norm(f"{p.first_name} {p.last_name}")
            except Exception:
                continue
            if full != target:
                continue
            c = getattr(p, "contract", None)
            if c is None:
                continue
            if clause == "NMC":
                c.no_movement_clause = True
                c.no_trade_clause = True  # NMC implies full trade protection
            elif clause == "NTC":
                c.no_trade_clause = True
            elif clause == "M-NTC":
                c.modified_ntc_teams = int(list_size or 0)
            # NMCs paired with a list size (e.g. Landeskog 12): the list is
            # the fallback frame for waiver discussions.
            if clause == "NMC" and list_size:
                c.modified_ntc_teams = int(list_size)
            stamped += 1
            break
    return stamped
