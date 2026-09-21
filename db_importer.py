# db_importer.py
# Updated to read the modern EHM SQLite (.db) format.

import sqlite3
from game_classes import Player, Team, League

# This dictionary maps the column names from the EHM database to our Player class attributes.
ATTRIBUTE_MAP = {
    'Skating': 'skating',
    'Strength': 'strength',
    'Shooting': 'shooting',
    'Passing': 'passing',
    'Stickhandling': 'deking',
    'OffensiveRead': 'offensive_awareness',
    'DefensiveRead': 'defensive_awareness',
    'Checking': 'checking',
    'Faceoffs': 'faceoffs',
    'Discipline': 'discipline',
    'ReboundControl': 'goaltending' # Simplified mapping for goalies
}

def load_league_from_db(filepath):
    """
    Connects to an EHM .db file and builds a League object from its data.
    """
    print(f"Attempting to connect to SQLite database: {filepath}")
    try:
        # Use Python's built-in sqlite3 library
        cnxn = sqlite3.connect(filepath)
        # This allows accessing columns by name
        cnxn.row_factory = sqlite3.Row 
        cursor = cnxn.cursor()
        print("Database connection successful.")

        new_league = League("Imported League")

        # --- 1. Read Teams ---
        print("Reading teams...")
        teams_map = {} # To quickly look up team objects by their DB ID
        cursor.execute("SELECT ClubID, Name, City FROM clubs")
        for row in cursor.fetchall():
            team = Team(team_name=row['Name'], city=row['City'])
            new_league.add_team(team)
            teams_map[row['ClubID']] = team
        print(f"Loaded {len(new_league.teams)} teams.")

        # --- 2. Read Players and Contracts ---
        print("Reading players and contracts...")
        sql = """
        SELECT p.FirstName, p.LastName, p.Position, p.Age, c.ClubID, c.Salary, c.ExpiryYear, p.*
        FROM players AS p
        LEFT JOIN contracts AS c ON p.PlayerID = c.PlayerID
        """
        cursor.execute(sql)
        for row in cursor.fetchall():
            pos_map = {0: "Goalie", 1: "Defenseman", 2: "Right Wing", 3: "Left Wing", 4: "Center"}
            position = pos_map.get(row['Position'], "Unknown")

            player = Player(
                first_name=row['FirstName'],
                last_name=row['LastName'],
                position=position,
                age=row['Age']
            )

            # Map attributes from the DB to the player object
            for db_col, py_attr in ATTRIBUTE_MAP.items():
                if db_col in row.keys():
                    setattr(player, py_attr, row[db_col])

            # Assign contract details
            player.salary = row['Salary'] if row['Salary'] is not None else 0
            if row['ExpiryYear']:
                player.contract_years = row['ExpiryYear'] - new_league.season_year
            else:
                player.contract_years = 0

            # Assign player to a team or free agents
            if row['ClubID'] in teams_map:
                team = teams_map[row['ClubID']]
                team.add_player(player)
            else:
                new_league.free_agents.append(player)
        
        print(f"Loaded {len(new_league.get_all_players())} total players.")
        cursor.close()
        cnxn.close()
        return new_league

    except sqlite3.Error as ex:
        print(f"Database Error Occurred: {ex}")
        print("Please ensure this is a valid EHM SQLite (.db) file.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

