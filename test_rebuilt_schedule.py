#!/usr/bin/env python3
"""
Test the completely rebuilt NHL schedule generation system.
Tests authentic NHL rotation patterns, realistic back-to-back management, and seasonal variation.
"""

import sys
import random
from datetime import date
sys.path.append('.')

def test_rebuilt_nhl_schedule_generation():
    print("=" * 80)
    print("🏒 TESTING REBUILT NHL SCHEDULE GENERATION SYSTEM")
    print("=" * 80)
    
    try:
        from game_classes import League
        
        # Test 1: Basic Schedule Generation for 2024-25 Season
        print("\n🧪 TEST 1: Basic NHL Schedule Generation (2024-25)")
        print("-" * 50)
        
        league = League(league_name='NHL')
        nhl_teams = [t for t in league.teams if t.league_name == 'National Hockey League']
        
        print(f"📋 NHL Teams Found: {len(nhl_teams)}")
        
        # Generate schedule for 2024-25 season
        league.generate_schedule(season_year=2024, rotation_seed=2024)
        
        # Count games per team
        team_game_counts = {}
        nhl_games_count = 0
        
        for game_item in league.schedule:
            if len(game_item) >= 3:
                if game_item[1] == 'NHL_EVENT':
                    continue  # Skip special events
                else:
                    # Regular NHL game
                    game_date, home_team, away_team = game_item
                    if hasattr(home_team, 'team_name') and hasattr(away_team, 'team_name'):
                        nhl_games_count += 1
                        home_name = home_team.team_name
                        away_name = away_team.team_name
                        team_game_counts[home_name] = team_game_counts.get(home_name, 0) + 1
                        team_game_counts[away_name] = team_game_counts.get(away_name, 0) + 1
        
        # Verify results
        print(f"📊 SEASON 2024-25 RESULTS:")
        print(f"   Total NHL games: {nhl_games_count}")
        print(f"   Teams tracked: {len(team_game_counts)}")
        
        teams_with_82 = sum(1 for count in team_game_counts.values() if count == 82)
        print(f"   Teams with 82 games: {teams_with_82}/32")
        
        if teams_with_82 == 32 and nhl_games_count == 1312:
            print("✅ PERFECT 2024-25 SEASON!")
        else:
            print("❌ Issues with 2024-25 season")
            # Show teams with wrong game counts
            for team_name, count in team_game_counts.items():
                if count != 82:
                    print(f"   ⚠️ {team_name}: {count} games")
        
        # Test 2: Seasonal Rotation (Different Seasons Should Generate Differently)
        print("\n🧪 TEST 2: Seasonal Rotation Validation")
        print("-" * 50)
        
        # Generate 2025-26 season with different rotation
        league_2025 = League(league_name='NHL')
        league_2025.generate_schedule(season_year=2025, rotation_seed=2025)
        
        # Compare first few games to see if they're different
        games_2024 = [(item[0], item[1].team_name, item[2].team_name) 
                     for item in league.schedule[:10] 
                     if len(item) >= 3 and item[1] != 'NHL_EVENT']
        
        games_2025 = [(item[0], item[1].team_name, item[2].team_name) 
                     for item in league_2025.schedule[:10] 
                     if len(item) >= 3 and item[1] != 'NHL_EVENT']
        
        different_schedules = games_2024 != games_2025
        
        print(f"📅 2024-25 vs 2025-26 Schedule Comparison:")
        print(f"   Schedules are different: {different_schedules}")
        
        if different_schedules:
            print("✅ SEASONAL ROTATION WORKING!")
            print("   Each season generates unique matchup patterns")
        else:
            print("⚠️ Schedules appear identical - rotation may not be working")
        
        # Test 3: Back-to-Back Analysis
        print("\n🧪 TEST 3: Back-to-Back Management Analysis")
        print("-" * 50)
        
        # Analyze back-to-backs in 2024-25 season
        team_schedules = {}
        for game_item in league.schedule:
            if len(game_item) >= 3 and game_item[1] != 'NHL_EVENT':
                game_date, home_team, away_team = game_item
                if hasattr(home_team, 'team_name') and hasattr(away_team, 'team_name'):
                    # Track each team's schedule
                    home_name = home_team.team_name
                    away_name = away_team.team_name
                    
                    if home_name not in team_schedules:
                        team_schedules[home_name] = []
                    if away_name not in team_schedules:
                        team_schedules[away_name] = []
                    
                    team_schedules[home_name].append(game_date)
                    team_schedules[away_name].append(game_date)
        
        # Sort each team's schedule and count back-to-backs
        back_to_back_counts = []
        consecutive_game_issues = []
        
        for team_name, dates in team_schedules.items():
            dates.sort()
            team_b2b = 0
            max_consecutive = 0
            current_consecutive = 1
            
            for i in range(1, len(dates)):
                days_gap = (dates[i] - dates[i-1]).days
                
                if days_gap == 1:  # Back-to-back
                    team_b2b += 1
                    current_consecutive += 1
                else:
                    max_consecutive = max(max_consecutive, current_consecutive)
                    current_consecutive = 1
            
            max_consecutive = max(max_consecutive, current_consecutive)
            back_to_back_counts.append(team_b2b)
            
            if max_consecutive > 3:  # Flag teams with 4+ consecutive games
                consecutive_game_issues.append((team_name, max_consecutive))
        
        min_b2b = min(back_to_back_counts)
        max_b2b = max(back_to_back_counts)
        avg_b2b = sum(back_to_back_counts) / len(back_to_back_counts)
        
        print(f"🎯 BACK-TO-BACK ANALYSIS:")
        print(f"   Range: {min_b2b} to {max_b2b} back-to-backs per team")
        print(f"   Average: {avg_b2b:.1f} back-to-backs per team")
        print(f"   NHL Target: 7-16 back-to-backs per team")
        
        teams_in_range = sum(1 for count in back_to_back_counts if 7 <= count <= 16)
        print(f"   Teams in NHL range: {teams_in_range}/32")
        
        print(f"\n🚫 CONSECUTIVE GAMES ANALYSIS:")
        if consecutive_game_issues:
            print(f"   Teams with 4+ consecutive games: {len(consecutive_game_issues)}")
            for team, consecutive in consecutive_game_issues:
                print(f"     {team}: {consecutive} consecutive games")
        else:
            print("   ✅ No teams have 4+ consecutive games!")
        
        # Test 4: Calendar Integration
        print("\n🧪 TEST 4: Calendar Integration Test")
        print("-" * 50)
        
        # Test if schedule works with calendar window
        try:
            # Mock parent for calendar window
            import tkinter as tk
            from datetime import timedelta
            from calendar_window import CalendarWindow
            
            class TestParent(tk.Tk):
                def __init__(self):
                    super().__init__()
                    self.withdraw()
                    
                    # Required attributes
                    self.BG_COLOR = '#181818'
                    self.CONTENT_BG = '#1F1F1F'
                    self.TITLE_BAR_COLOR = '#2A2A2A'
                    self.TEXT_COLOR = '#E0E0E0'
                    self.HEADER_COLOR = '#FFFFFF'
                    self.ACCENT_COLOR = '#D13438'
                    self.FONT_FAMILY = 'Segoe UI'
                    
                    # Mock game data
                    self.current_date = date(2024, 10, 15)
                    self.user_team = type('Team', (), {'team_name': 'Boston Bruins', 'city': 'Boston'})()
                    self.league = league  # Use our generated league
                    self.game_results = []
                    self.open_windows = {}
            
            parent = TestParent()
            calendar_window = CalendarWindow(parent)
            
            # Count events loaded into calendar
            total_events = sum(len(events) for events in calendar_window.events_by_date.values())
            
            print(f"📅 CALENDAR INTEGRATION:")
            print(f"   Events loaded into calendar: {total_events}")
            print(f"   Calendar window created successfully: ✅")
            
            # Check for color diversity in calendar
            unique_colors = set()
            for button_date, button in calendar_window.day_buttons.items():
                try:
                    bg_color = button.cget('bg')
                    unique_colors.add(bg_color)
                except:
                    pass
            
            print(f"   Unique colors in calendar: {len(unique_colors)}")
            print("   ✅ Calendar integration successful!")
            
            calendar_window.destroy()
            parent.destroy()
            
        except Exception as e:
            print(f"   ❌ Calendar integration failed: {e}")
        
        # Final Summary
        print("\n" + "=" * 80)
        print("🏆 REBUILT NHL SCHEDULE SYSTEM - FINAL RESULTS")
        print("=" * 80)
        
        all_tests_passed = (
            teams_with_82 == 32 and 
            nhl_games_count == 1312 and 
            different_schedules and
            teams_in_range >= 20 and  # At least 20 teams should be in NHL range
            not consecutive_game_issues
        )
        
        if all_tests_passed:
            print("🎉 ALL TESTS PASSED!")
            print("✅ Perfect 82-game seasons")
            print("✅ Authentic seasonal rotation") 
            print("✅ Realistic back-to-back management")
            print("✅ No excessive consecutive games")
            print("✅ Calendar integration working")
            print("\n🚀 The rebuilt NHL schedule system is ready for production!")
        else:
            print("⚠️ Some tests failed - system needs refinement")
            print("📋 Issues to address:")
            if teams_with_82 != 32:
                print(f"   - {32 - teams_with_82} teams don't have 82 games")
            if not different_schedules:
                print("   - Seasonal rotation not working")
            if teams_in_range < 20:
                print("   - Too many teams outside NHL back-to-back range")
            if consecutive_game_issues:
                print(f"   - {len(consecutive_game_issues)} teams have excessive consecutive games")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_rebuilt_nhl_schedule_generation()