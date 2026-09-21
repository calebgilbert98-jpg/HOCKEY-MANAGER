# Hockey Manager AI Assistant Guidelines

## Project Overview
Hockey Manager is a sports management simulation game inspired by Eastside Hockey Manager. The application allows users to manage a hockey team, handling roster moves, player development, contracts, scheduling, and game simulations with a visual game viewer.

## Architecture

### Core Components
- **`main.py`**: Entry point containing the `GameManager` and `HockeyManagerGUI` classes. The main controller for game state and UI.
- **`game_classes.py`**: Contains the data models for `Player`, `Team`, `League`, `Contract`, etc. using dataclasses with type hints.
- **`windows.py`**: UI window classes for different game features (roster, trade, scouting, etc.) that follow a consistent inheritance pattern.
- **`GAME_VIEWER.py`**: Visual game simulation renderer using Tkinter that animates games based on event logs.
- **`simulation.py`**: Game simulation engine with `GameSim` class for simulating hockey games based on player attributes.
- **`draft_generator.py`**: Creates randomized draft classes with varied player attributes using archetypes and tiered potential.
- **`db_importer.py`**: Utility for importing team/player data from external databases (SQLite format).
- **`ui_components.py`**: Reusable UI components like `PlayerProfileWindow` that can be used across multiple windows.

### Data Flow
1. `GameManager` initializes and maintains the game state, including teams, players, and the schedule
2. `HockeyManagerGUI` renders the main interface and manages user interactions through multiple specialized windows
3. Game actions (like continuing to the next day) trigger simulation in `AdvancedGameSim`, which updates team/player data
4. UI components use the `update_views()` pattern to refresh displayed data after state changes
5. Windows access data through their `parent` reference, which ultimately points to the main `HockeyManagerGUI` instance
6. The game state persists in memory during runtime (no database persistence yet)

## Development Patterns

### Player Attributes
Players have numerous attributes that influence their performance:
- **Technical skills**: skating, shooting, passing, checking, faceoffs, etc.
- **Mental attributes**: determination, teamwork, leadership, discipline, flair, etc.
- **Physical attributes**: strength, injury_proneness, etc.
- **Advanced attributes**: vision, hockey IQ, puck protection, shooting_accuracy, etc.
- **Role-specific attributes**: reflexes, positioning, rebound_control for goalies

Each attribute uses a 1-20 scale, with most randomly generated between 5-20 during initialization:

```python
# Example of adding a new player attribute
class Player:
    # Existing attributes...
    new_attribute: int = field(default_factory=lambda: random.randint(5, 20))
```

These attributes are used in the `overall_rating()` method with position-specific weightings. When adding new attributes, also update this method to incorporate them into player ratings:

```python
def overall_rating(self) -> int:
    if self.primary_position == PlayerPosition.GOALIE:
        rating = (
            self.goaltending * 0.15 +
            self.reflexes * 0.15 +
            # Add your new goalie attribute here with appropriate weight
            self.new_attribute * 0.05
        )
    # Handle other positions similarly...
```

### Game Simulation
The game simulation system (`AdvancedGameSim` in `main.py` and `GameSim` in `simulation.py`) uses an event-based approach:

1. **Event Generation**: Player attributes determine the probability and outcome of events:
   ```python
   # Example: Shot outcome using player attributes
   shot_skill = (
       shooter.shooting_accuracy * 0.3 +
       shooter.shooting_power * 0.2 +
       shooter.composure * 0.15 +
       shooter.vision * 0.15 +
       shooter.hockey_iq * 0.2
   ) * fatigue_factor
   ```

2. **Randomization**: Events include randomness to create variability:
   ```python
   # Add randomness to skills
   shot_chance = 0.08 + (shot_skill - goalie_skill) * 0.002
   if random.random() < shot_chance:
       # Process goal
   ```

3. **Event Logging**: Events are recorded for replay and statistics:
   ```python
   self.event_log.append({
       'timestamp': self.time,
       'duration': duration,
       'type': 'SHOT',
       'details': {
           'shooter_id': shooter.id,
           'puck_start_pos': shot_start,
           'result': shot_result
       }
   })
   ```

4. **Game State Tracking**: Position of players, puck, and game clock are tracked:
   ```python
   state = {
       'home': [{'id': p.id, 'x': p.x, 'y': p.y} for p in home_players],
       'away': [{'id': p.id, 'x': p.x, 'y': p.y} for p in away_players],
       'puck': {'x': self.puck_x, 'y': self.puck_y},
       'time': self.time,
       'period': self.period
   }
   ```

### UI Components
All UI components follow a consistent pattern:
- Inherit from `tk.Toplevel`
- Take a `parent` parameter (usually the main app)
- Include an `update_views()` method for refreshing data
- Follow the styling of parent using `parent.BG_COLOR`, `parent.FONT_FAMILY`, etc.

```python
class NewFeatureWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("New Feature")
        self.configure(background=parent.BG_COLOR)
        # Create UI elements...
        
    def update_views(self):
        # Refresh UI with latest data...
```

When creating UI components:
- Use the `_create_panel()` helper for consistent panel styling
- Use `_create_treeview()` for standardized tables with context menus
- Store tree data in `parent.tree_maps` to associate UI elements with data objects
- Add your new window to `parent.open_windows` for lifecycle management

```python
# Example of creating a treeview
columns = {'id': ('ID', 50), 'name': ('Name', 200), 'stat': ('Stat', 80)}
self.my_tree = parent._create_treeview(self, columns, height=15)
parent._populate_player_tree(self.my_tree, players_list)

# Adding window to tracked windows
self.parent.open_windows['my_feature'] = self
```

## Common Workflows

### Adding a New Feature
1. Determine if it requires a new window or can be added to existing UI
2. Add relevant data structures to `game_classes.py` if needed
3. Create UI components in either `windows.py` or `ui_components.py`
4. Add navigation method in `HockeyManagerGUI`
5. Connect to simulation logic if needed

Example workflow for adding a new "Player Training" feature:

```python
# 1. Add to game_classes.py
@dataclass
class TrainingSession:
    player: Player
    focus_attribute: str
    duration_days: int
    
# 2. Create window in windows.py
class TrainingWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Training Center")
        self.configure(background=parent.BG_COLOR)
        # UI implementation...
        
    def update_views(self):
        # Refresh with current training data
    
    def assign_training(self, player, attribute):
        # Training logic
        
# 3. Add navigation in main.py
def open_training_window(self):
    if 'training' not in self.open_windows or not self.open_windows['training'].winfo_exists():
        self.open_windows['training'] = TrainingWindow(self)
    self.open_windows['training'].focus_set()
```

### Debugging Game Simulation
- Add print statements in the `GameSim` class to track event generation and resolution
- Check event logs for unexpected behavior using `sim.game_log` or `event_log`
- Verify player attributes are being used correctly in skill calculations
- Use the `GAME_VIEWER` to visualize game events by inspecting the event structure:

```python
# Example of debugging a simulation issue
def _resolve_scoring_chance(self, shooter, attacking_team, defending_team):
    print(f"DEBUG: Scoring chance by {shooter.full_name}")
    print(f"Shooter skill values: shooting={shooter.shooting}, vision={shooter.vision}")
    
    # ...calculation logic...
    
    print(f"Shot roll: {shot_roll}, Save roll: {save_roll}")
    if shot_roll > save_roll:
        print("GOAL!")
    else:
        print("SAVE!")
```

To debug the game viewer, examine the event_log structure for timestamp issues or missing fields:

```python
# Check event structure before passing to game viewer
for event in sim.event_log[:5]:  # First 5 events
    print(json.dumps(event, indent=2))
```

### Visual Design
The app uses a dark theme with consistent styling:
- Dark backgrounds (`#181818`, `#1F1F1F`)
- Light text (`#E0E0E0`, `#FFFFFF`)
- Accent color (`#D13438`) for buttons and highlights
- All fonts use "Segoe UI" family

Style constants are defined in `HockeyManagerGUI._setup_styles()`:

```python
def _setup_styles(self):
    self.BG_COLOR = '#181818'
    self.CONTENT_BG = '#1F1F1F'
    self.TITLE_BAR_COLOR = '#2A2A2A'
    self.TEXT_COLOR = '#E0E0E0'
    self.HEADER_COLOR = '#FFFFFF'
    self.ACCENT_COLOR = '#D13438'
    self.ACCENT_ACTIVE = '#A1272A'
    self.ACCENT_HOVER = '#E54E52'
    
    # Style configuration follows...
```

When creating new UI elements, always use these predefined styles rather than hardcoding colors:

```python
# Correct
panel = ttk.Frame(self, style='Panel.TFrame')
ttk.Label(panel, text="Stats", style='Title.TLabel')
ttk.Button(panel, text="Update", style='TButton')

# Incorrect - avoid hardcoding colors
panel = ttk.Frame(self, background='#222222')  # Wrong
ttk.Label(panel, text="Stats", foreground='white')  # Wrong
```

## Key Conventions

### Roster Management
- Players exist in one of four states: NHL roster, AHL roster, Prospects, or Free Agents
- Moving players between these lists should update their `team_name` property
- Player contracts must be respected when signing/trading
- Use the Team class methods for roster management:

```python
# Correct way to add a player to a team
team.add_player(player, "roster")  # or "ahl" or "prospects"

# Correct way to remove a player from a team
team.remove_player(player)  # Handles NHL/AHL/prospects automatically
```

### Player Ratings
- Overall ratings are calculated based on weighted position-specific attributes
- Always use the `player.overall_rating()` method, never hardcode rating calculations
- Position-specific weighting is handled inside the rating method:

```python
# Calculate player's rating
rating = player.overall_rating()  # Correct

# Incorrect - don't calculate ratings manually
manual_rating = (player.shooting * 0.3 + player.passing * 0.2)  # Wrong
```

### Game Simulation
When creating new game events or enhancing simulation:
- Use player attributes to determine outcomes
- Add randomness for unpredictability
- Record events in the log for user feedback
- Consider visual representation in the game viewer

Event structure for the game viewer must follow this format:
```python
{
    'timestamp': float,  # When the event starts (in seconds)
    'duration': float,   # How long the event lasts
    'type': str,         # Event type: 'SHOT', 'PASS', 'SKATE', 'STOPPAGE', etc.
    'details': {         # Event-specific data
        # Relevant fields for the event type
        # Common fields:
        'player_id': str,  # ID of the player involved
        'puck_start_pos': tuple,  # Starting position (x, y)
        'result': str,  # Outcome of the event (e.g., 'GOAL', 'SAVE')
    }
}
```

## Development and Implementation Standards

### Code Quality Requirements

#### Thorough Implementation
- **Comprehensive Data Access**: Always verify the correct data structure and access patterns before implementation
  - Check for existing similar patterns in the codebase (e.g., using `team.roster` vs `team.players["roster"]`)
  - Verify class attributes by examining existing code that interacts with those classes
- **Method Naming Consistency**: Follow existing naming conventions for methods and properties
  - If adding new methods, ensure their names align with existing ones
  - Be consistent with naming (e.g., if the codebase uses `get_players()`, don't create a `fetch_players()` method)

#### Error Handling
- Implement proper error handling for UI interactions
- Add appropriate validation for user inputs
- Handle edge cases for empty collections and invalid states
- Use try/except blocks for operations that could fail (file I/O, parsing, etc.)

#### Data Structure Validation
- When working with collections or dictionaries:
  - Verify key existence before access (use `.get()` or `try/except`)
  - Check for empty collections before iteration
  - Use defensive programming with fallback values
  ```python
  # Example of safe property access
  salary = getattr(player, "salary", getattr(player.contract, "salary", 750000))
  ```

### Testing and Quality Assurance

#### Unit Testing
- Test individual components in isolation:
  ```python
  # Manual testing for new functions
  def test_calculate_market_value():
      player = Player(...)  # Create test player
      result = calculate_market_value(player)
      print(f"Market value for {player.full_name}: ${result:,}")
      
      # Test edge cases
      young_player = Player(...)
      young_player.age = 18
      print(f"Young player value: ${calculate_market_value(young_player):,}")
  ```

#### Integration Testing
- Test interactions between components:
  - Verify data flows correctly between objects
  - Test that UI components correctly update when the underlying data changes
  - Validate that changes in one component properly affect other components

#### UI Testing
- Create test scenarios for UI components:
  - Test user workflows from start to finish
  - Verify that the UI responds correctly to user input
  - Check for visual consistency with the rest of the application

### Implementation Workflow

1. **Understand the Request**: Fully understand the feature request and its context
2. **Research Existing Patterns**: Examine how similar features are implemented
3. **Plan Your Implementation**: Design the solution using consistent patterns
4. **Initial Implementation**: Create the code with thorough error handling
5. **Validation**: Test the implementation with various scenarios and edge cases
6. **Refinement**: Refine the implementation based on testing results
7. **Documentation**: Add comments and documentation for complex logic

### Debugging Strategy

1. **Identify Error Cause**: 
   - Read error messages carefully to understand root causes
   - Trace the error back to its source (variable, method, class)
   - Check related components that might be affecting the issue

2. **Evidence Collection**:
   - Use `print()` statements to output relevant values at key points
   - Trace data flow through the application
   - Confirm assumptions about object structures and values

3. **Fix Implementation**:
   - Make precise, targeted changes to address the specific issue
   - Check for similar issues elsewhere in the codebase
   - Ensure fix doesn't introduce new problems

4. **Verify Solution**:
   - Test the fix with multiple scenarios
   - Verify that the original error no longer occurs
   - Check for any performance impacts or side effects

### Documentation Requirements

- Add docstrings to all new methods and classes:
  ```python
  def calculate_market_value(self, player):
      """Calculate a player's market value based on attributes and age.
      
      Args:
          player: The Player object to evaluate
          
      Returns:
          int: The calculated market value in dollars
      """
  ```
- Include comments for complex logic blocks
- Document any assumptions or limitations in your implementation
- Add usage examples for new public methods
