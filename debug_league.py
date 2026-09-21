#!/usr/bin/env python3
"""
Simple test to diagnose the League class issue.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from game_classes import League

# Test League creation
print("Testing League creation...")

try:
    nhl = League(league_name="NHL", season_year=2024)
    print("✅ League created with keyword arguments")
    print(f"   league_name: {nhl.league_name}")
    print(f"   season_year: {nhl.season_year}")
    print(f"   teams type: {type(nhl.teams)}")
    print(f"   teams value: {nhl.teams}")
except Exception as e:
    print(f"❌ Failed with keyword args: {e}")

try:
    nhl2 = League("NHL", 2024)
    print("✅ League created with positional arguments")
    print(f"   league_name: {nhl2.league_name}")
    print(f"   season_year: {nhl2.season_year}")  
    print(f"   teams type: {type(nhl2.teams)}")
    print(f"   teams value: {nhl2.teams}")
except Exception as e:
    print(f"❌ Failed with positional args: {e}")
    import traceback
    traceback.print_exc()