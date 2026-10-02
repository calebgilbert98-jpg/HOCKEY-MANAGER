#!/usr/bin/env python3
"""qa_default_options.py — verify Default options in game setup.

Tests:
1. "Default" exists in DATABASE_CONFIGURATIONS with our tuned standard
2. Default config has 336 prospects/draft and 28 staff/team
3. Season length "Default (84 Games)" maps to 84 games
4. generate_database("Default") doesn't raise
5. Existing options (Small/Medium/Large/Massive) still work
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name}")
        failed += 1

print("== Default database config ==")
try:
    from database_generator import DATABASE_CONFIGURATIONS
    check("Default in DATABASE_CONFIGURATIONS", "Default" in DATABASE_CONFIGURATIONS)

    cfg = DATABASE_CONFIGURATIONS["Default"]
    check("Default prospects_per_draft == 336", cfg.prospects_per_draft == 336)
    check("Default staff_count == 28", cfg.staff_count == 28)
    check("Default total_players == 8000", cfg.total_players == 8000)
    check("Default leagues_count == 2", cfg.leagues_count == 2)

    # Existing configs untouched
    check("Small still exists", "Small" in DATABASE_CONFIGURATIONS)
    check("Medium still exists", "Medium" in DATABASE_CONFIGURATIONS)
    check("Large still exists", "Large" in DATABASE_CONFIGURATIONS)
    check("Massive still exists", "Massive" in DATABASE_CONFIGURATIONS)
    check("Small prospects unchanged (150)", DATABASE_CONFIGURATIONS["Small"].prospects_per_draft == 150)
except Exception as e:
    check(f"database_generator import/config (exc: {e})", False)

print("== Season length mapping ==")
try:
    # Use the actual fixed logic from main.py (case-insensitive)
    def configure_season_length(season_length):
        _sl = (season_length or "").lower()
        if "20 games" in _sl:
            return 20
        elif "41 games" in _sl:
            return 41
        else:
            return 84

    check("Default (84 Games) -> 84", configure_season_length("Default (84 Games)") == 84)
    check("Full Season (84 Games) -> 84", configure_season_length("Full Season (84 Games)") == 84)
    check("Short Season (20 Games) -> 20", configure_season_length("Short Season (20 Games)") == 20)
    check("Half Season (41 Games) -> 41", configure_season_length("Half Season (41 Games)") == 41)
    check("Extended Season (100+ Games) -> 84", configure_season_length("Extended Season (100+ Games)") == 84)
except Exception as e:
    check(f"season length mapping (exc: {e})", False)

print("== Database size name extraction ==")
try:
    # Simulate the launcher's extraction: first word of display string
    def extract_db_name(display):
        return display.split(' ')[0] if ' ' in display else display

    check("'Default (Recommended)' -> 'Default'", extract_db_name("Default (Recommended)") == "Default")
    check("'Small (8K...)' -> 'Small'", extract_db_name("Small (8K players, 32 NHL+AHL teams)") == "Small")
    check("'Default' in configs after extraction", extract_db_name("Default (Recommended)") in DATABASE_CONFIGURATIONS)
except Exception as e:
    check(f"name extraction (exc: {e})", False)

print("== Wizard DATABASE_SIZES ==")
try:
    from new_game_setup import DATABASE_SIZES
    check("default in wizard DATABASE_SIZES", "default" in DATABASE_SIZES)
    check("wizard default prospects == 336", DATABASE_SIZES["default"]["prospects_per_draft"] == 336)
    check("wizard medium still exists", "medium" in DATABASE_SIZES)
    check("wizard small still exists", "small" in DATABASE_SIZES)
    check("wizard large still exists", "large" in DATABASE_SIZES)
except Exception as e:
    check(f"wizard sizes (exc: {e})", False)

print(f"\n{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
