"""
Comprehensive Save/Load System for Hockey Manager
Handles saving and loading complete game states including players, teams, leagues, and progress
"""

import pickle
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional
import gzip
import threading
from dataclasses import asdict
import sys


class GameSaveManager:
    """Manages saving and loading of complete game states"""
    
    def __init__(self, game_manager):
        self.game_manager = game_manager
        self.save_directory = "saves"
        self.autosave_enabled = True
        self.autosave_frequency = 7  # Days between autosaves
        self.last_autosave = None
        
        # Ensure save directory exists
        if not os.path.exists(self.save_directory):
            os.makedirs(self.save_directory)
    
    def create_save_data(self) -> Dict[str, Any]:
        """Create a complete save data structure"""
        try:
            save_data = {
                'version': '1.0',
                'timestamp': datetime.now().isoformat(),
                'game_date': self.game_manager.current_date.isoformat() if hasattr(self.game_manager, 'current_date') else None,
                'season_year': getattr(self.game_manager.league, 'season_year', 2024) if hasattr(self.game_manager, 'league') else 2024,
                'user_team': self.game_manager.user_team.team_name if hasattr(self.game_manager, 'user_team') and self.game_manager.user_team else None,
                
                # League data
                'league': self._serialize_league(),
                
                # Game state
                'current_date': self.game_manager.current_date.isoformat() if hasattr(self.game_manager, 'current_date') else None,
                'schedule': self._serialize_schedule(),
                'game_results': getattr(self.game_manager, 'game_results', []),
                
                # Settings and preferences
                'settings': self._get_current_settings(),
                
                # Statistics and records
                'player_stats_history': getattr(self.game_manager, 'player_stats_history', {}),
                'team_stats_history': getattr(self.game_manager, 'team_stats_history', {}),
                
                # Draft and prospects
                'draft_classes': getattr(self.game_manager, 'draft_classes', {}),
                'scouting_reports': getattr(self.game_manager, 'scouting_reports', {}),
                
                # Free agency and waivers
                'free_agents': self._serialize_free_agents(),
                'waiver_claims': getattr(self.game_manager, 'waiver_claims', []),
                
                # Trade and contract data
                'trade_history': getattr(self.game_manager, 'trade_history', []),
                'contract_negotiations': getattr(self.game_manager, 'contract_negotiations', {}),
                
                # Email and communication
                'inbox_messages': getattr(self.game_manager, 'inbox_messages', []),
                'news_stories': getattr(self.game_manager, 'news_stories', []),
            }

            # FM-style career state (board, training, reputation, press history)
            try:
                gm = self.game_manager
                career = getattr(gm, 'career', None)
                if career is None:
                    career = getattr(getattr(gm, 'game_manager', None), 'career', None)
                save_data['career_data'] = career.to_dict() if career else {}
            except Exception as e:
                print(f"Could not save career data: {e}")
                save_data['career_data'] = {}
            
            return save_data
            
        except Exception as e:
            print(f"Error creating save data: {e}")
            raise
    
    def _serialize_league(self) -> Dict[str, Any]:
        """Serialize league data including all teams and players"""
        if not hasattr(self.game_manager, 'league') or not self.game_manager.league:
            return {}
        
        league = self.game_manager.league
        league_data = {
            'league_name': getattr(league, 'league_name', 'NHL'),
            'season_year': league.season_year,
            'teams': [],  # teams is a list, not dict
            'standings': getattr(league, 'standings', {}),
            'schedule_generated': getattr(league, 'schedule_generated', False),
        }
        
        # Serialize all teams
        for team in league.teams:
            team_data = self._serialize_team(team)
            if team_data:
                league_data['teams'].append(team_data)
        
        return league_data
    
    def _serialize_team(self, team) -> Dict[str, Any]:
        """Serialize a team including all players and stats"""
        try:
            team_data = {
                'team_name': team.team_name,
                'city': team.city,
                'roster': [self._serialize_player(p) for p in getattr(team, 'roster', [])],
                'ahl_roster': [self._serialize_player(p) for p in getattr(team, 'ahl_roster', [])],
                'prospects': [self._serialize_player(p) for p in getattr(team, 'prospects', [])],
                'coaching_staff': getattr(team, 'coaching_staff', []),
                'stats': self._serialize_team_stats(getattr(team, 'stats', None)),
                'salary_cap_info': getattr(team, 'salary_cap_info', {}),
                'draft_picks': getattr(team, 'draft_picks', {}),
                'trade_block': getattr(team, 'trade_block', []),
                'division': getattr(team, 'division', ''),
                'conference': getattr(team, 'conference', ''),
                'standings_position': getattr(team, 'standings_position', 0),
            }
            
            return team_data
            
        except Exception as e:
            print(f"Error serializing team {team.team_name}: {e}")
            return {}
    
    def _serialize_player(self, player) -> Dict[str, Any]:
        """Serialize a player with all attributes"""
        try:
            # Convert player to dictionary, handling dataclass if necessary
            if hasattr(player, '__dict__'):
                player_data = {}
                for key, value in player.__dict__.items():
                    if key == 'contract' and value:
                        # Special handling for contract objects
                        player_data[key] = self._serialize_contract(value)
                    elif key == 'stats' and value:
                        # Special handling for stats objects
                        player_data[key] = self._serialize_player_stats(value)
                    elif isinstance(value, (date, datetime)):
                        # Handle date/datetime objects
                        player_data[key] = value.isoformat()
                    elif hasattr(value, 'name'):  # Enum handling
                        player_data[key] = value.name
                    else:
                        player_data[key] = value
                
                return player_data
            else:
                return {}
                
        except Exception as e:
            print(f"Error serializing player: {e}")
            return {}
    
    def _serialize_contract(self, contract) -> Dict[str, Any]:
        """Serialize a contract object"""
        try:
            if hasattr(contract, '__dict__'):
                contract_data = {}
                for key, value in contract.__dict__.items():
                    if isinstance(value, (date, datetime)):
                        contract_data[key] = value.isoformat()
                    else:
                        contract_data[key] = value
                return contract_data
            return {}
        except Exception as e:
            print(f"Error serializing contract: {e}")
            return {}
    
    def _serialize_player_stats(self, stats) -> Dict[str, Any]:
        """Serialize player statistics"""
        try:
            if hasattr(stats, '__dict__'):
                return {k: v for k, v in stats.__dict__.items()}
            return {}
        except Exception as e:
            print(f"Error serializing player stats: {e}")
            return {}
    
    def _serialize_team_stats(self, stats) -> Dict[str, Any]:
        """Serialize team statistics"""
        try:
            if hasattr(stats, '__dict__'):
                return {k: v for k, v in stats.__dict__.items()}
            return {}
        except Exception as e:
            print(f"Error serializing team stats: {e}")
            return {}
    
    def _serialize_schedule(self) -> list:
        """Serialize the game schedule"""
        try:
            if not hasattr(self.game_manager, 'league') or not hasattr(self.game_manager.league, 'schedule'):
                return []
            
            schedule_data = []
            for game in self.game_manager.league.schedule:
                try:
                    if isinstance(game, dict):
                        game_date = game.get('date')
                        home_team = game.get('home_team')
                        away_team = game.get('away_team')
                        league = game.get('league', '')
                        # Skip special events here (handled separately)
                        if home_team == 'NHL_EVENT' or away_team == 'NHL_EVENT':
                            continue
                    elif isinstance(game, (tuple, list)) and len(game) >= 3:
                        game_date, home_team, away_team = game[0], game[1], game[2]
                        if home_team == 'NHL_EVENT':
                            continue
                        league = getattr(home_team, 'league_name', '')
                        league = {'National Hockey League': 'NHL',
                                  'American Hockey League': 'AHL'}.get(league, league)
                    else:
                        continue
                    schedule_data.append({
                        'date': game_date.isoformat() if hasattr(game_date, 'isoformat') else str(game_date),
                        'home_team': home_team.team_name if hasattr(home_team, 'team_name') else str(home_team),
                        'away_team': away_team.team_name if hasattr(away_team, 'team_name') else str(away_team),
                        'league': league,
                    })
                except (AttributeError, TypeError, IndexError):
                    continue
            
            return schedule_data
            
        except Exception as e:
            print(f"Error serializing schedule: {e}")
            return []
    
    def _serialize_free_agents(self) -> list:
        """Serialize free agent players"""
        try:
            if hasattr(self.game_manager, 'free_agents'):
                return [self._serialize_player(p) for p in self.game_manager.free_agents]
            return []
        except Exception as e:
            print(f"Error serializing free agents: {e}")
            return []
    
    def _get_current_settings(self) -> Dict[str, Any]:
        """Get current game settings"""
        try:
            settings = {}
            
            # Get settings from the main game manager
            if hasattr(self.game_manager, 'settings'):
                settings.update(self.game_manager.settings)
            
            # Get UI settings if available
            if hasattr(self.game_manager, 'ui_settings'):
                settings.update(self.game_manager.ui_settings)
            
            return settings
            
        except Exception as e:
            print(f"Error getting settings: {e}")
            return {}
    
    def save_game(self, filename: Optional[str] = None, compress: bool = True) -> bool:
        """Save the complete game state to a file"""
        try:
            if not filename:
                # Generate default filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                user_team = "Unknown"
                if hasattr(self.game_manager, 'user_team') and self.game_manager.user_team:
                    user_team = self.game_manager.user_team.team_name.replace(" ", "_")
                
                filename = f"{user_team}_{timestamp}.hm"
            
            filepath = os.path.join(self.save_directory, filename)
            
            # Create save data
            save_data = self.create_save_data()
            
            # Save with compression
            if compress:
                with gzip.open(filepath, 'wb') as f:
                    pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            else:
                with open(filepath, 'wb') as f:
                    pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            print(f"Game saved successfully to: {filepath}")
            self.last_autosave = datetime.now()
            return True
            
        except Exception as e:
            print(f"Error saving game: {e}")
            messagebox.showerror("Save Error", f"Failed to save game: {str(e)}")
            return False
    
    def save_enhanced_game(self, filename: str, compress: bool = True, enhanced_data: dict = None, custom_filepath: str = None) -> bool:
        """Save the complete game state with enhanced metadata"""
        try:
            filepath = custom_filepath or os.path.join(self.save_directory, filename)
            
            # Create enhanced save data
            save_data = self.create_save_data()
            
            # Add enhanced metadata
            if enhanced_data:
                save_data['enhanced_data'] = enhanced_data
                save_data['enhanced_version'] = '2.0'
            
            # Save screenshot if requested
            if enhanced_data and enhanced_data.get('screenshot', False):
                try:
                    screenshot_data = self._capture_screenshot()
                    if screenshot_data:
                        save_data['screenshot'] = screenshot_data
                except Exception as e:
                    print(f"Failed to capture screenshot: {e}")
            
            # Save with compression
            if compress:
                with gzip.open(filepath, 'wb') as f:
                    pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            else:
                with open(filepath, 'wb') as f:
                    pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            print(f"Enhanced game saved successfully to: {filepath}")
            self.last_autosave = datetime.now()
            return True
            
        except Exception as e:
            print(f"Error saving enhanced game: {e}")
            messagebox.showerror("Save Error", f"Failed to save game: {str(e)}")
            return False
    
    def _capture_screenshot(self):
        """Capture a screenshot of the main window for save preview"""
        try:
            # This would capture a screenshot of the main window
            # For now, return None as this requires additional implementation
            return None
        except Exception as e:
            print(f"Screenshot capture failed: {e}")
            return None
    
    def _load_save_metadata(self, filepath: str) -> dict:
        """Load only the metadata from a save file without loading the full game"""
        try:
            save_data = None
            
            # Try compressed first
            try:
                with gzip.open(filepath, 'rb') as f:
                    save_data = pickle.load(f)
            except:
                try:
                    with open(filepath, 'rb') as f:
                        save_data = pickle.load(f)
                except Exception:
                    return None
            
            if save_data:
                # Return only metadata, not the full game data
                metadata = {
                    'version': save_data.get('version', 'Unknown'),
                    'timestamp': save_data.get('timestamp', 'Unknown'),
                    'user_team': save_data.get('user_team', 'Unknown'),
                    'season_year': save_data.get('season_year', 'Unknown'),
                    'game_date': save_data.get('game_date', 'Unknown'),
                    'enhanced_data': save_data.get('enhanced_data', {}),
                    'enhanced_version': save_data.get('enhanced_version', '1.0')
                }
                return metadata
            
            return None
            
        except Exception as e:
            print(f"Error loading save metadata: {e}")
            return None
    
    def get_save_files(self) -> list:
        """Get list of save files with enhanced metadata"""
        save_files = []
        
        try:
            # Get files from main save directory
            self._scan_directory_for_saves(self.save_directory, save_files)
            
            # Also scan subdirectories for categorized saves
            for item in os.listdir(self.save_directory):
                item_path = os.path.join(self.save_directory, item)
                if os.path.isdir(item_path):
                    self._scan_directory_for_saves(item_path, save_files, category=item)
            
        except Exception as e:
            print(f"Error scanning save files: {e}")
        
        # Sort by modification time (newest first)
        save_files.sort(key=lambda x: x['modified'], reverse=True)
        
        return save_files
    
    def _scan_directory_for_saves(self, directory: str, save_files: list, category: str = "General"):
        """Scan a directory for save files"""
        try:
            for filename in os.listdir(directory):
                if filename.endswith('.hm'):
                    filepath = os.path.join(directory, filename)
                    stat = os.stat(filepath)
                    
                    # Load metadata for enhanced info
                    metadata = self._load_save_metadata(filepath)
                    
                    file_info = {
                        'filename': filename,
                        'filepath': filepath,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime),
                        'is_autosave': 'autosave' in filename.lower() or 'auto' in filename.lower(),
                        'category': category,
                        'description': '',
                        'team': 'Unknown',
                        'game_date': 'Unknown'
                    }
                    
                    # Add enhanced metadata if available
                    if metadata:
                        enhanced = metadata.get('enhanced_data', {})
                        file_info.update({
                            'description': enhanced.get('description', ''),
                            'team': metadata.get('user_team', 'Unknown'),
                            'game_date': metadata.get('game_date', 'Unknown')
                        })
                    
                    save_files.append(file_info)
                    
        except Exception as e:
            print(f"Error scanning directory {directory}: {e}")
    
    def load_game(self, filepath: str) -> bool:
        """Load a complete game state from a file"""
        try:
            if not os.path.exists(filepath):
                messagebox.showerror("Load Error", f"Save file not found: {filepath}")
                return False
            
            # Try to load compressed first, then uncompressed
            save_data = None
            try:
                with gzip.open(filepath, 'rb') as f:
                    save_data = pickle.load(f)
            except:
                try:
                    with open(filepath, 'rb') as f:
                        save_data = pickle.load(f)
                except Exception as e:
                    messagebox.showerror("Load Error", f"Failed to load save file: {str(e)}")
                    return False
            
            if not save_data:
                messagebox.showerror("Load Error", "Invalid save file format")
                return False
            
            # Restore game state
            success = self._restore_game_state(save_data)
            
            if success:
                print(f"Game loaded successfully from: {filepath}")
                messagebox.showinfo("Load Complete", "Game loaded successfully!")
                
                # Update UI if available
                if hasattr(self.game_manager, 'update_all_views'):
                    self.game_manager.update_all_views()
                
                return True
            else:
                messagebox.showerror("Load Error", "Failed to restore game state")
                return False
            
        except Exception as e:
            print(f"Error loading game: {e}")
            messagebox.showerror("Load Error", f"Failed to load game: {str(e)}")
            return False
    
    def _restore_game_state(self, save_data: Dict[str, Any]) -> bool:
        """Restore the complete game state from save data"""
        try:
            # Check save version compatibility
            version = save_data.get('version', '1.0')
            if not self._is_compatible_version(version):
                messagebox.showwarning("Version Warning", 
                                     f"Save file version {version} may not be fully compatible")
            
            # Restore basic game state
            if 'current_date' in save_data and save_data['current_date']:
                self.game_manager.current_date = datetime.fromisoformat(save_data['current_date']).date()
            
            # Restore league
            if 'league' in save_data:
                self._restore_league(save_data['league'])
            
            # Restore user team
            if 'user_team' in save_data and save_data['user_team']:
                self._restore_user_team(save_data['user_team'])
            
            # Restore schedule
            if 'schedule' in save_data:
                self._restore_schedule(save_data['schedule'])
            
            # Restore game results
            if 'game_results' in save_data:
                self.game_manager.game_results = save_data['game_results']
            
            # Restore other game data
            for key in ['player_stats_history', 'team_stats_history', 'draft_classes', 
                       'scouting_reports', 'waiver_claims', 'trade_history', 
                       'contract_negotiations', 'inbox_messages', 'news_stories']:
                if key in save_data:
                    setattr(self.game_manager, key, save_data[key])

            # Restore FM-style career state
            if save_data.get('career_data'):
                try:
                    from manager_career import CareerState
                    target = self.game_manager
                    # Career lives on the GameManager; SaveLoadWindow may wrap the GUI
                    if not hasattr(target, 'user_team') and hasattr(target, 'game_manager'):
                        target = target.game_manager
                    target.career = CareerState.from_dict(save_data['career_data'])
                except Exception as e:
                    print(f"Could not restore career data: {e}")
            
            # Restore free agents
            if 'free_agents' in save_data:
                self._restore_free_agents(save_data['free_agents'])
            
            # Restore settings
            if 'settings' in save_data:
                self._restore_settings(save_data['settings'])
            
            return True
            
        except Exception as e:
            print(f"Error restoring game state: {e}")
            return False
    
    def _restore_league(self, league_data: Dict[str, Any]):
        """Restore league data"""
        try:
            from game_classes import League, Team
            
            # Create or update league
            if not hasattr(self.game_manager, 'league') or not self.game_manager.league:
                self.game_manager.league = League(
                    league_name=league_data.get('league_name', 'NHL'),
                    season_year=league_data.get('season_year', 2024)
                )
            
            league = self.game_manager.league
            league.league_name = league_data.get('league_name', 'NHL')
            league.season_year = league_data.get('season_year', 2024)
            league.standings = league_data.get('standings', {})
            league.schedule_generated = league_data.get('schedule_generated', False)
            
            # Restore teams (clear existing and restore from save)
            league.teams.clear()
            teams_data = league_data.get('teams', [])
            
            for team_data in teams_data:
                team = self._restore_team(team_data)
                if team:
                    league.teams.append(team)
            
        except Exception as e:
            print(f"Error restoring league: {e}")
    
    def _restore_team(self, team_data: Dict[str, Any]):
        """Restore a team from save data"""
        try:
            from game_classes import Team
            from types import SimpleNamespace
            
            team = Team(
                team_data.get('team_name', ''),
                team_data.get('city', ''),
                team_data.get('division', ''),
                team_data.get('conference', ''),
            )
            
            # Restore basic team info
            team.division = team_data.get('division', '')
            team.conference = team_data.get('conference', '')
            team.standings_position = team_data.get('standings_position', 0)
            team.coaching_staff = team_data.get('coaching_staff', [])
            team.salary_cap_info = team_data.get('salary_cap_info', {})
            team.draft_picks = team_data.get('draft_picks', {})
            team.trade_block = team_data.get('trade_block', [])
            
            # Restore team stats
            if 'stats' in team_data:
                team.stats = self._restore_team_stats(team_data['stats'])
            else:
                team.stats = SimpleNamespace()
            
            # Restore players
            team.roster = [self._restore_player(p) for p in team_data.get('roster', [])]
            team.ahl_roster = [self._restore_player(p) for p in team_data.get('ahl_roster', [])]
            team.prospects = [self._restore_player(p) for p in team_data.get('prospects', [])]
            
            # Filter out None players
            team.roster = [p for p in team.roster if p is not None]
            team.ahl_roster = [p for p in team.ahl_roster if p is not None]
            team.prospects = [p for p in team.prospects if p is not None]
            
            return team
            
        except Exception as e:
            print(f"Error restoring team: {e}")
            return None
    
    def _restore_player(self, player_data: Dict[str, Any]):
        """Restore a player from save data"""
        try:
            from game_classes import Player, PlayerStats, Contract, PlayerPosition
            
            if not player_data:
                return None

            # Resolve primary position first (required positional arg)
            pos_value = player_data.get('primary_position')
            try:
                primary_position = PlayerPosition[pos_value] if isinstance(pos_value, str) else pos_value
            except Exception:
                primary_position = PlayerPosition.CENTER  # Default
            if primary_position is None:
                primary_position = PlayerPosition.CENTER

            # Create player with basic info
            player = Player(
                player_data.get('first_name', ''),
                player_data.get('last_name', ''),
                player_data.get('age', 25),
                primary_position,
            )
            
            # Restore all player attributes
            for key, value in player_data.items():
                if key in ['first_name', 'last_name', 'age', 'primary_position']:
                    continue  # Already set
                elif key == 'contract' and value:
                    player.contract = self._restore_contract(value)
                elif key == 'stats' and value:
                    player.stats = self._restore_player_stats(value)
                elif key.endswith('_date') and value:
                    # Handle date fields
                    try:
                        setattr(player, key, datetime.fromisoformat(value).date())
                    except:
                        pass
                else:
                    setattr(player, key, value)
            
            return player
            
        except Exception as e:
            print(f"Error restoring player: {e}")
            return None
    
    def _restore_contract(self, contract_data: Dict[str, Any]):
        """Restore a contract from save data"""
        try:
            from game_classes import Contract
            
            contract = Contract(
                contract_data.get('salary', 750000),
                contract_data.get('years_remaining', 1)
            )
            
            # Restore other contract fields
            for key, value in contract_data.items():
                if key in ['salary', 'years_remaining']:
                    continue
                elif key.endswith('_date') and value:
                    try:
                        setattr(contract, key, datetime.fromisoformat(value).date())
                    except:
                        pass
                else:
                    setattr(contract, key, value)
            
            return contract
            
        except Exception as e:
            print(f"Error restoring contract: {e}")
            return None
    
    def _restore_player_stats(self, stats_data: Dict[str, Any]):
        """Restore player statistics"""
        try:
            from game_classes import PlayerStats
            
            stats = PlayerStats()
            
            for key, value in stats_data.items():
                setattr(stats, key, value)
            
            return stats
            
        except Exception as e:
            print(f"Error restoring player stats: {e}")
            from game_classes import PlayerStats
            return PlayerStats()
    
    def _restore_team_stats(self, stats_data: Dict[str, Any]):
        """Restore team statistics"""
        try:
            from types import SimpleNamespace
            
            stats = SimpleNamespace()
            
            for key, value in stats_data.items():
                setattr(stats, key, value)
            
            return stats
            
        except Exception as e:
            print(f"Error restoring team stats: {e}")
            from types import SimpleNamespace
            return SimpleNamespace()
    
    def _restore_user_team(self, user_team_name: str):
        """Restore the user's selected team"""
        try:
            if hasattr(self.game_manager, 'league') and self.game_manager.league:
                for team in self.game_manager.league.teams:
                    if team.team_name == user_team_name:
                        self.game_manager.user_team = team
                        break
        except Exception as e:
            print(f"Error restoring user team: {e}")
    
    def _restore_schedule(self, schedule_data: list):
        """Restore the game schedule"""
        try:
            if not hasattr(self.game_manager, 'league') or not self.game_manager.league:
                return
            
            schedule = []
            for game_data in schedule_data:
                try:
                    game_date = datetime.fromisoformat(game_data['date']).date()
                    
                    # Find teams by name
                    home_team = None
                    away_team = None
                    
                    for team in self.game_manager.league.teams:
                        if team.team_name == game_data['home_team']:
                            home_team = team
                        if team.team_name == game_data['away_team']:
                            away_team = team
                    
                    if home_team and away_team:
                        from datetime import time as dt_time
                        schedule.append({
                            'date': game_date,
                            'home_team': home_team,
                            'away_team': away_team,
                            'time': dt_time(19, 0),
                            'league': game_data.get('league', ''),
                        })
                except:
                    continue
            
            self.game_manager.league.schedule = schedule
            
        except Exception as e:
            print(f"Error restoring schedule: {e}")
    
    def _restore_free_agents(self, free_agents_data: list):
        """Restore free agent players"""
        try:
            free_agents = []
            for player_data in free_agents_data:
                player = self._restore_player(player_data)
                if player:
                    free_agents.append(player)
            
            self.game_manager.free_agents = free_agents
            
        except Exception as e:
            print(f"Error restoring free agents: {e}")
    
    def _restore_settings(self, settings_data: Dict[str, Any]):
        """Restore game settings"""
        try:
            if not hasattr(self.game_manager, 'settings'):
                self.game_manager.settings = {}
            
            self.game_manager.settings.update(settings_data)
            
        except Exception as e:
            print(f"Error restoring settings: {e}")
    
    def _is_compatible_version(self, version: str) -> bool:
        """Check if save file version is compatible"""
        # For now, accept all versions
        return True
    
    def autosave(self):
        """Perform an automatic save if needed"""
        try:
            if not self.autosave_enabled:
                return
            
            current_time = datetime.now()
            
            # Check if autosave is needed
            if self.last_autosave is None:
                time_since_last = timedelta(days=999)  # Force first autosave
            else:
                time_since_last = current_time - self.last_autosave
            
            if time_since_last.days >= self.autosave_frequency:
                # Generate autosave filename
                timestamp = current_time.strftime("%Y%m%d_%H%M%S")
                autosave_filename = f"autosave_{timestamp}.hm"
                
                # Perform autosave in background thread
                def background_save():
                    success = self.save_game(autosave_filename)
                    if success:
                        print(f"Autosave completed: {autosave_filename}")
                
                save_thread = threading.Thread(target=background_save, daemon=True)
                save_thread.start()
        
        except Exception as e:
            print(f"Error during autosave: {e}")
    
    def get_save_files(self) -> list:
        """Get list of available save files"""
        try:
            save_files = []
            
            if os.path.exists(self.save_directory):
                for filename in os.listdir(self.save_directory):
                    if filename.endswith('.hm'):
                        filepath = os.path.join(self.save_directory, filename)
                        stat = os.stat(filepath)
                        
                        save_files.append({
                            'filename': filename,
                            'filepath': filepath,
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime),
                            'is_autosave': filename.startswith('autosave_')
                        })
            
            # Sort by modification time (newest first)
            save_files.sort(key=lambda x: x['modified'], reverse=True)
            
            return save_files
            
        except Exception as e:
            print(f"Error getting save files: {e}")
            return []


class SaveLoadWindow(tk.Toplevel):
    """UI window for saving and loading games"""
    
    def __init__(self, parent, mode='save'):
        super().__init__(parent)
        self.parent = parent
        self.mode = mode  # 'save' or 'load'
        self.save_manager = GameSaveManager(parent)
        self.save_completed = False  # Flag for exit handling
        self.loaded_file_path = None  # For load mode integration
        self.was_cancelled = False  # Track if dialog was cancelled
        
        self.title(f"{'Save' if mode == 'save' else 'Load'} Game")
        self.configure(background=parent.BG_COLOR)
        self.geometry("800x600")
        
        # Set up proper close protocol to handle X button clicks
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)
        
        # Make dialog modal
        self.transient(parent)
        self.grab_set()
        
        self._create_interface()
        self._refresh_file_list()
    
    def on_window_close(self):
        """Handle window close events (X button, Alt+F4, etc.)"""
        # Set appropriate flags based on whether save was completed
        if not self.save_completed:
            self.was_cancelled = True
        
        # Release modal grab safely
        try:
            self.grab_release()
        except Exception:
            pass
        
        # Destroy window safely
        try:
            self.destroy()
        except Exception:
            pass
    
    def _create_interface(self):
        """Create the save/load interface"""
        main_frame = ttk.Frame(self, style='Content.TFrame')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        title_text = f"{'💾 Save Game' if self.mode == 'save' else '📁 Load Game'}"
        title_label = ttk.Label(main_frame, text=title_text, style='Title.TLabel',
                               font=(self.parent.FONT_FAMILY, 20, 'bold'))
        title_label.pack(pady=(0, 20))
        
        if self.mode == 'save':
            self._create_save_interface(main_frame)
        else:
            self._create_load_interface(main_frame)
    
    def _create_save_interface(self, parent):
        """Create enhanced save game interface"""
        # Create notebook for organized save interface
        save_notebook = ttk.Notebook(parent, style='TNotebook')
        save_notebook.pack(fill='both', expand=True)
        
        # Quick Save Tab
        quick_tab = ttk.Frame(save_notebook, style='Content.TFrame')
        save_notebook.add(quick_tab, text="Quick Save")
        self._create_quick_save_tab(quick_tab)
        
        # Advanced Save Tab
        advanced_tab = ttk.Frame(save_notebook, style='Content.TFrame')
        save_notebook.add(advanced_tab, text="Advanced Save")
        self._create_advanced_save_tab(advanced_tab)
        
        # Manage Saves Tab
        manage_tab = ttk.Frame(save_notebook, style='Content.TFrame')
        save_notebook.add(manage_tab, text="Manage Saves")
        self._create_manage_saves_tab(manage_tab)
    
    def _create_quick_save_tab(self, parent):
        """Create quick save interface"""
        # Game preview
        preview_frame = ttk.LabelFrame(parent, text="Current Game", style='Card.TLabelframe')
        preview_frame.pack(fill='x', padx=10, pady=10)
        
        preview_content = self._get_game_preview()
        preview_label = ttk.Label(preview_frame, text=preview_content, 
                                 style='Content.TLabel', justify='left')
        preview_label.pack(padx=10, pady=10, anchor='w')
        
        # Quick save slots
        slots_frame = ttk.LabelFrame(parent, text="Quick Save Slots", style='Card.TLabelframe')
        slots_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self._create_quick_save_slots(slots_frame)
        
        # Quick save buttons
        quick_buttons_frame = ttk.Frame(parent, style='Content.TFrame')
        quick_buttons_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(quick_buttons_frame, text="❌ Cancel", 
                  command=self.on_window_close, 
                  style='TButton').pack(side='right')
    
    def _create_advanced_save_tab(self, parent):
        """Create advanced save interface with full customization"""
        # Save naming section
        naming_frame = ttk.LabelFrame(parent, text="Save Details", style='Card.TLabelframe')
        naming_frame.pack(fill='x', padx=10, pady=10)
        
        # Save name with suggestions
        name_row = ttk.Frame(naming_frame, style='Content.TFrame')
        name_row.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(name_row, text="Save Name:", style='Content.TLabel').pack(side='left')
        
        self.save_name_var = tk.StringVar()
        name_entry = ttk.Entry(name_row, textvariable=self.save_name_var, 
                              style='TEntry', width=30)
        name_entry.pack(side='left', padx=(10, 5))
        
        # Generate suggested names
        suggestions_btn = ttk.Button(name_row, text="Suggestions", 
                                   command=self._show_name_suggestions,
                                   style='TButton')
        suggestions_btn.pack(side='left', padx=5)
        
        # Set default name
        self._set_default_save_name()
        
        # Save description
        desc_row = ttk.Frame(naming_frame, style='Content.TFrame')
        desc_row.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(desc_row, text="Description:", style='Content.TLabel').pack(anchor='w')
        
        self.description_text = tk.Text(desc_row, height=3, width=50, wrap='word',
                                       font=(self.parent.FONT_FAMILY, 9))
        self.description_text.pack(fill='x', pady=(5, 0))
        
        # Save category/folder
        category_row = ttk.Frame(naming_frame, style='Content.TFrame')
        category_row.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(category_row, text="Category:", style='Content.TLabel').pack(side='left')
        
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(category_row, textvariable=self.category_var,
                                     values=self._get_save_categories(),
                                     style='TCombobox', width=20)
        category_combo.pack(side='left', padx=(10, 0))
        category_combo.set("General")
        
        # Save options
        options_frame = ttk.LabelFrame(parent, text="Save Options", style='Card.TLabelframe')
        options_frame.pack(fill='x', padx=10, pady=10)
        
        options_grid = ttk.Frame(options_frame, style='Content.TFrame')
        options_grid.pack(fill='x', padx=10, pady=10)
        
        self.compress_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_grid, text="Compress save file (recommended)", 
                       variable=self.compress_var, style='TCheckbutton').grid(row=0, column=0, sticky='w')
        
        self.backup_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_grid, text="Create backup of existing save", 
                       variable=self.backup_var, style='TCheckbutton').grid(row=1, column=0, sticky='w')
        
        self.auto_screenshot_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_grid, text="Save screenshot for preview", 
                       variable=self.auto_screenshot_var, style='TCheckbutton').grid(row=0, column=1, sticky='w', padx=(20, 0))
        
        self.include_stats_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_grid, text="Include detailed statistics", 
                       variable=self.include_stats_var, style='TCheckbutton').grid(row=1, column=1, sticky='w', padx=(20, 0))
        
        # Save buttons
        buttons_frame = ttk.Frame(parent, style='Content.TFrame')
        buttons_frame.pack(fill='x', padx=10, pady=10)
        
        save_btn = ttk.Button(buttons_frame, text="💾 Save Game", 
                             command=self._advanced_save_game, 
                             style='Accent.TButton')
        save_btn.pack(side='left', padx=(0, 10))
        
        save_as_btn = ttk.Button(buttons_frame, text="💾 Save As...", 
                                command=self._save_as_dialog, 
                                style='TButton')
        save_as_btn.pack(side='left', padx=(0, 10))
        
        cancel_btn = ttk.Button(buttons_frame, text="❌ Cancel", 
                               command=self.on_window_close, 
                               style='TButton')
        cancel_btn.pack(side='right')
    
    def _create_manage_saves_tab(self, parent):
        """Create save file management interface"""
        # File operations toolbar
        toolbar_frame = ttk.Frame(parent, style='Content.TFrame')
        toolbar_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(toolbar_frame, text="🗂️ Open Save Folder", 
                  command=self._open_save_folder, style='TButton').pack(side='left', padx=(0, 5))
        
        ttk.Button(toolbar_frame, text="📤 Export Save", 
                  command=self._export_save, style='TButton').pack(side='left', padx=5)
        
        ttk.Button(toolbar_frame, text="📥 Import Save", 
                  command=self._import_save, style='TButton').pack(side='left', padx=5)
        
        ttk.Button(toolbar_frame, text="🗑️ Delete Selected", 
                  command=self._delete_selected_save, style='TButton').pack(side='left', padx=5)
        
        # Enhanced file list with more details
        self._create_enhanced_file_list(parent, "Save File Manager")
    
    def _create_quick_save_slots(self, parent):
        """Create quick save slots interface"""
        slots_info = self._get_quick_save_slots()
        
        for i in range(6):  # 6 quick save slots
            slot_frame = ttk.Frame(parent, style='Content.TFrame')
            slot_frame.pack(fill='x', padx=10, pady=5)
            
            slot_info = slots_info.get(f"slot_{i+1}", {})
            
            # Slot number
            slot_label = ttk.Label(slot_frame, text=f"Slot {i+1}:", 
                                  style='Content.TLabel', width=8)
            slot_label.pack(side='left')
            
            if slot_info:
                # Existing save
                info_text = f"{slot_info['name']} - {slot_info['date']} - {slot_info['team']}"
                info_label = ttk.Label(slot_frame, text=info_text, 
                                      style='Content.TLabel', width=50)
                info_label.pack(side='left', padx=(5, 0))
                
                ttk.Button(slot_frame, text="💾 Overwrite", 
                          command=lambda s=i+1: self._quick_save_to_slot(s),
                          style='TButton').pack(side='right', padx=(0, 5))
                
                ttk.Button(slot_frame, text="📁 Load", 
                          command=lambda s=i+1: self._quick_load_from_slot(s),
                          style='TButton').pack(side='right', padx=5)
            else:
                # Empty slot
                empty_label = ttk.Label(slot_frame, text="<Empty Slot>", 
                                       style='Content.TLabel', foreground='gray')
                empty_label.pack(side='left', padx=(5, 0))
                
                ttk.Button(slot_frame, text="💾 Save Here", 
                          command=lambda s=i+1: self._quick_save_to_slot(s),
                          style='TButton').pack(side='right')
    
    def _create_enhanced_file_list(self, parent, title):
        """Create enhanced file list with more details"""
        list_frame = ttk.LabelFrame(parent, text=title, style='Card.TLabelframe')
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Enhanced columns with more information
        columns = {
            'filename': ('File Name', 180),
            'description': ('Description', 200),
            'team': ('Team', 120),
            'date': ('Game Date', 100),
            'size': ('Size', 80),
            'modified': ('Last Modified', 130),
            'category': ('Category', 80),
            'type': ('Type', 80),
            'filepath': ('', 0)  # Hidden column for storing file paths
        }
        
        self.file_tree = ttk.Treeview(list_frame, columns=list(columns.keys()), 
                                     show='headings', height=12)
        
        for col_id, (header, width) in columns.items():
            self.file_tree.heading(col_id, text=header, command=lambda c=col_id: self._sort_files(c))
            self.file_tree.column(col_id, width=width, anchor='w')
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.file_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient='horizontal', command=self.file_tree.xview)
        self.file_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.file_tree.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        v_scrollbar.grid(row=0, column=1, sticky='ns', pady=10)
        h_scrollbar.grid(row=1, column=0, sticky='ew', padx=10)
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Context menu for file operations
        self._create_file_context_menu()
        
        # Bind selection event
        self.file_tree.bind('<<TreeviewSelect>>', self._on_enhanced_file_select)
        self.file_tree.bind('<Double-1>', self._on_file_double_click)
        self.file_tree.bind('<Button-3>', self._show_file_context_menu)
    
    def _create_load_interface(self, parent):
        """Create load game interface"""
        # Load instructions
        instruction_label = ttk.Label(parent, 
                                    text="Select a save file to load:",
                                    style='Content.TLabel')
        instruction_label.pack(pady=(0, 10))
        
        # File list
        self._create_file_list(parent, "Available Save Files")
        
        # Load buttons
        load_buttons_frame = ttk.Frame(parent, style='Content.TFrame')
        load_buttons_frame.pack(fill='x', pady=(10, 0))
        
        self.load_btn = ttk.Button(load_buttons_frame, text="📁 Load Selected Game", 
                                  command=self._load_game, style='Accent.TButton',
                                  state='disabled')
        self.load_btn.pack(side='left')
        
        cancel_btn = ttk.Button(load_buttons_frame, text="❌ Cancel", 
                               command=self.on_window_close, 
                               style='TButton')
        cancel_btn.pack(side='right')
    
    def _create_file_list(self, parent, title):
        """Create the file list display"""
        list_frame = ttk.LabelFrame(parent, text=title, style='Card.TLabelframe')
        list_frame.pack(fill='both', expand=True, pady=(10, 0))
        
        # Create treeview for file list
        columns = {
            'filename': ('File Name', 200),
            'size': ('Size', 80),
            'modified': ('Last Modified', 150),
            'type': ('Type', 80)
        }
        
        self.file_tree = ttk.Treeview(list_frame, columns=list(columns.keys()), 
                                     show='headings', height=15)
        
        for col_id, (header, width) in columns.items():
            self.file_tree.heading(col_id, text=header)
            self.file_tree.column(col_id, width=width, anchor='w')
        
        # Scrollbar for file list
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        
        self.file_tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side='right', fill='y', pady=10)
        
        # Bind selection event for load mode
        if self.mode == 'load':
            self.file_tree.bind('<<TreeviewSelect>>', self._on_file_select)
            self.file_tree.bind('<Double-1>', self._on_file_double_click)
    
    def _refresh_file_list(self):
        """Refresh the list of save files with enhanced information"""
        # Clear existing items
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        # Get save files with enhanced metadata
        save_files = self.save_manager.get_save_files()
        
        for save_file in save_files:
            filename = save_file['filename']
            description = save_file.get('description', '')[:50] + ('...' if len(save_file.get('description', '')) > 50 else '')
            team = save_file.get('team', 'Unknown')
            game_date = save_file.get('game_date', 'Unknown')
            if game_date != 'Unknown' and len(game_date) > 10:
                try:
                    game_date = game_date[:10]  # Show just the date part
                except:
                    pass
            
            size_mb = round(save_file['size'] / (1024 * 1024), 2)
            modified = save_file['modified'].strftime("%m/%d %H:%M")
            category = save_file.get('category', 'General')
            file_type = "Autosave" if save_file['is_autosave'] else "Manual"
            
            values = (filename, description, team, game_date, f"{size_mb} MB", modified, category, file_type)
            
            item_id = self.file_tree.insert('', 'end', values=values)
            # Store full file info as item data
            self.file_tree.set(item_id, 'filepath', save_file['filepath'])
    
    def _on_file_select(self, event):
        """Handle file selection in load mode"""
        if self.mode == 'load':
            selection = self.file_tree.selection()
            self.load_btn.config(state='normal' if selection else 'disabled')
    
    def _on_file_double_click(self, event):
        """Handle double-click on file in load mode"""
        if self.mode == 'load':
            self._load_game()
    
    def _save_game(self):
        """Save the current game using basic interface"""
        save_name = self.save_name_var.get().strip()
        if not save_name:
            messagebox.showerror("Error", "Please enter a save name")
            return
        
        # Add .hm extension if not present
        if not save_name.endswith('.hm'):
            save_name += '.hm'
        
        # Check if file already exists
        filepath = os.path.join(self.save_manager.save_directory, save_name)
        if os.path.exists(filepath):
            result = messagebox.askyesno("File Exists", 
                                       f"Save file '{save_name}' already exists. Overwrite?")
            if not result:
                return
        
        # Perform save
        success = self.save_manager.save_game(save_name, self.compress_var.get())
        
        if success:
            messagebox.showinfo("Save Complete", f"Game saved successfully as '{save_name}'")
            self._refresh_file_list()
            self.save_completed = True  # Flag for exit handling
            self.parent.on_game_saved()
            # Close the dialog after successful save
            self.on_window_close()
        else:
            messagebox.showerror("Save Failed", "Failed to save game")
    
    def _advanced_save_game(self):
        """Save game with advanced options"""
        save_name = self.save_name_var.get().strip()
        if not save_name:
            messagebox.showerror("Error", "Please enter a save name")
            return
        
        # Add .hm extension if not present
        if not save_name.endswith('.hm'):
            save_name += '.hm'
        
        # Create category folder if needed
        category = self.category_var.get().strip()
        if category and category != "General":
            category_dir = os.path.join(self.save_manager.save_directory, category)
            if not os.path.exists(category_dir):
                os.makedirs(category_dir)
            filepath = os.path.join(category_dir, save_name)
        else:
            filepath = os.path.join(self.save_manager.save_directory, save_name)
        
        # Check if file already exists and handle backup
        if os.path.exists(filepath):
            if self.backup_var.get():
                backup_name = f"{save_name}.backup"
                backup_path = os.path.join(os.path.dirname(filepath), backup_name)
                try:
                    import shutil
                    shutil.copy2(filepath, backup_path)
                    print(f"Backup created: {backup_path}")
                except Exception as e:
                    print(f"Failed to create backup: {e}")
            
            result = messagebox.askyesno("File Exists", 
                                       f"Save file '{save_name}' already exists. Overwrite?")
            if not result:
                return
        
        # Prepare enhanced save data
        enhanced_data = {
            'description': self.description_text.get('1.0', 'end-1c').strip(),
            'category': category,
            'include_stats': self.include_stats_var.get(),
            'screenshot': self.auto_screenshot_var.get()
        }
        
        # Perform enhanced save
        success = self.save_manager.save_enhanced_game(save_name, 
                                                      self.compress_var.get(), 
                                                      enhanced_data, 
                                                      filepath)
        
        if success:
            messagebox.showinfo("Save Complete", f"Game saved successfully as '{save_name}'")
            self._refresh_file_list()
            self.save_completed = True  # Flag for exit handling
            self.parent.on_game_saved()
            # Close the dialog after successful save
            self.on_window_close()
        else:
            messagebox.showerror("Save Failed", "Failed to save game")
    
    def _save_as_dialog(self):
        """Open save as dialog"""
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            title="Save Game As...",
            defaultextension=".hm",
            filetypes=[("Hockey Manager Save", "*.hm"), ("All Files", "*.*")],
            initialdir=self.save_manager.save_directory
        )
        
        if filename:
            # Extract just the filename for the entry
            import os
            base_name = os.path.basename(filename)
            self.save_name_var.set(base_name.replace('.hm', ''))
            self._advanced_save_game()
    
    def _quick_save_to_slot(self, slot_number):
        """Save to a quick save slot"""
        slot_name = f"QuickSave_Slot_{slot_number}"
        
        # Create quick save data
        enhanced_data = {
            'description': f"Quick Save Slot {slot_number}",
            'category': 'QuickSaves',
            'include_stats': True,
            'screenshot': False,
            'slot_number': slot_number
        }
        
        # Ensure QuickSaves directory exists
        quick_saves_dir = os.path.join(self.save_manager.save_directory, "QuickSaves")
        if not os.path.exists(quick_saves_dir):
            os.makedirs(quick_saves_dir)
        
        filepath = os.path.join(quick_saves_dir, f"{slot_name}.hm")
        
        success = self.save_manager.save_enhanced_game(slot_name + ".hm", True, enhanced_data, filepath)
        
        if success:
            messagebox.showinfo("Quick Save", f"Game saved to Quick Save Slot {slot_number}")
            self._refresh_quick_save_slots()
            self.save_completed = True  # Flag for exit handling
            self.parent.on_game_saved()
            # Close the dialog after successful quick save
            self.on_window_close()
        else:
            messagebox.showerror("Quick Save Failed", f"Failed to save to slot {slot_number}")
    
    def _quick_load_from_slot(self, slot_number):
        """Load from a quick save slot"""
        slot_name = f"QuickSave_Slot_{slot_number}.hm"
        filepath = os.path.join(self.save_manager.save_directory, "QuickSaves", slot_name)
        
        if os.path.exists(filepath):
            self.save_manager.load_game(filepath)
        else:
            messagebox.showerror("Load Error", f"Quick Save Slot {slot_number} is empty")
    
    def _get_game_preview(self):
        """Get current game state preview"""
        try:
            preview_lines = []
            
            if hasattr(self.parent, 'user_team') and self.parent.user_team:
                preview_lines.append(f"Team: {self.parent.user_team.team_name}")
                
                # Add roster info
                roster_count = len(getattr(self.parent.user_team, 'roster', []))
                preview_lines.append(f"Roster Size: {roster_count} players")
            
            if hasattr(self.parent, 'current_date'):
                preview_lines.append(f"Current Date: {self.parent.current_date}")
            
            if hasattr(self.parent, 'league') and self.parent.league:
                preview_lines.append(f"Season: {getattr(self.parent.league, 'season_year', 'Unknown')}")
            
            # Add record if available
            if hasattr(self.parent, 'user_team') and self.parent.user_team:
                wins = getattr(self.parent.user_team, 'wins', 0)
                losses = getattr(self.parent.user_team, 'losses', 0)
                preview_lines.append(f"Record: {wins}-{losses}")
            
            return "\n".join(preview_lines) if preview_lines else "Game information not available"
            
        except Exception as e:
            return f"Error getting game preview: {str(e)}"
    
    def _set_default_save_name(self):
        """Set a smart default save name"""
        suggestions = self._generate_name_suggestions()
        if suggestions:
            self.save_name_var.set(suggestions[0])
        else:
            # Fallback to timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.save_name_var.set(f"HockeyManager_{timestamp}")
    
    def _generate_name_suggestions(self):
        """Generate smart save name suggestions"""
        suggestions = []
        
        try:
            # Base info
            team_name = "HockeyManager"
            if hasattr(self.parent, 'user_team') and self.parent.user_team:
                team_name = self.parent.user_team.team_name.replace(" ", "_")
            
            # Date info
            now = datetime.now()
            date_str = now.strftime("%Y%m%d")
            time_str = now.strftime("%H%M")
            
            # Game date if available
            game_date_str = ""
            if hasattr(self.parent, 'current_date'):
                game_date_str = self.parent.current_date.strftime("%m_%d")
            
            # Season info
            season_str = ""
            if hasattr(self.parent, 'league') and self.parent.league:
                season_str = f"_{getattr(self.parent.league, 'season_year', '')}"
            
            # Generate suggestions
            suggestions.extend([
                f"{team_name}_{date_str}_{time_str}",
                f"{team_name}_Season{season_str}_{game_date_str}" if season_str and game_date_str else f"{team_name}_{date_str}",
                f"{team_name}_Backup_{date_str}",
                f"{team_name}_Milestone_{date_str}",
                f"Save_{team_name}_{now.strftime('%b%d')}"
            ])
            
            # Filter out empty suggestions
            suggestions = [s for s in suggestions if s and not s.endswith('_')]
            
        except Exception as e:
            print(f"Error generating suggestions: {e}")
            suggestions = [f"HockeyManager_{datetime.now().strftime('%Y%m%d_%H%M%S')}"]
        
        return suggestions[:5]  # Return top 5 suggestions
    
    def _show_name_suggestions(self):
        """Show save name suggestions dialog"""
        suggestions = self._generate_name_suggestions()
        
        # Create suggestion window
        suggestion_window = tk.Toplevel(self)
        suggestion_window.title("Save Name Suggestions")
        suggestion_window.geometry("400x300")
        suggestion_window.configure(background=self.parent.BG_COLOR)
        
        ttk.Label(suggestion_window, text="Choose a save name:", 
                 style='Content.TLabel').pack(pady=10)
        
        # Suggestions listbox
        listbox_frame = ttk.Frame(suggestion_window, style='Content.TFrame')
        listbox_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        suggestions_listbox = tk.Listbox(listbox_frame, height=10,
                                        font=(self.parent.FONT_FAMILY, 10))
        suggestions_listbox.pack(fill='both', expand=True)
        
        for suggestion in suggestions:
            suggestions_listbox.insert('end', suggestion)
        
        # Buttons
        button_frame = ttk.Frame(suggestion_window, style='Content.TFrame')
        button_frame.pack(pady=10)
        
        def use_selected():
            selection = suggestions_listbox.curselection()
            if selection:
                self.save_name_var.set(suggestions[selection[0]])
            suggestion_window.destroy()
        
        ttk.Button(button_frame, text="Use Selected", command=use_selected,
                  style='Accent.TButton').pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=suggestion_window.destroy,
                  style='TButton').pack(side='left', padx=5)
        
        # Select first suggestion by default
        if suggestions:
            suggestions_listbox.selection_set(0)
    
    def _get_save_categories(self):
        """Get list of save categories"""
        categories = ["General", "Milestones", "Backups", "Experiments", "Seasons"]
        
        # Add existing categories from save directory
        try:
            save_dir = self.save_manager.save_directory
            if os.path.exists(save_dir):
                for item in os.listdir(save_dir):
                    item_path = os.path.join(save_dir, item)
                    if os.path.isdir(item_path) and item not in categories:
                        categories.append(item)
        except Exception as e:
            print(f"Error reading categories: {e}")
        
        return sorted(categories)
    
    def _get_quick_save_slots(self):
        """Get information about quick save slots"""
        slots = {}
        quick_saves_dir = os.path.join(self.save_manager.save_directory, "QuickSaves")
        
        if os.path.exists(quick_saves_dir):
            for i in range(1, 7):  # Slots 1-6
                slot_file = f"QuickSave_Slot_{i}.hm"
                slot_path = os.path.join(quick_saves_dir, slot_file)
                
                if os.path.exists(slot_path):
                    try:
                        # Get file info
                        stat = os.stat(slot_path)
                        modified = datetime.fromtimestamp(stat.st_mtime)
                        
                        # Try to get save data for more info
                        save_data = self.save_manager._load_save_metadata(slot_path)
                        team_name = save_data.get('user_team', 'Unknown') if save_data else 'Unknown'
                        
                        slots[f"slot_{i}"] = {
                            'name': f"Quick Save {i}",
                            'date': modified.strftime("%m/%d %H:%M"),
                            'team': team_name,
                            'filepath': slot_path
                        }
                    except Exception as e:
                        print(f"Error reading slot {i}: {e}")
        
        return slots
    
    def _refresh_quick_save_slots(self):
        """Refresh the quick save slots display"""
        # This would be called to update the quick save slots UI
        # For now, we'll implement this when the tab is visible
        pass
    
    def _open_save_folder(self):
        """Open the saves folder in file explorer"""
        import subprocess
        import os
        
        save_dir = self.save_manager.save_directory
        if os.path.exists(save_dir):
            try:
                # Windows
                if os.name == 'nt':
                    subprocess.run(['explorer', save_dir])
                # macOS
                elif os.name == 'posix' and 'darwin' in os.uname().sysname.lower():
                    subprocess.run(['open', save_dir])
                # Linux
                else:
                    subprocess.run(['xdg-open', save_dir])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open save folder: {e}")
        else:
            messagebox.showerror("Error", "Save folder does not exist")
    
    def _export_save(self):
        """Export selected save file"""
        selection = self.file_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a save file to export")
            return
        
        # Get selected file path
        item = selection[0]
        filepath = self.file_tree.set(item, 'filepath')
        
        # Ask for export location
        from tkinter import filedialog
        export_path = filedialog.asksaveasfilename(
            title="Export Save File",
            defaultextension=".hm",
            filetypes=[("Hockey Manager Save", "*.hm"), ("All Files", "*.*")]
        )
        
        if export_path:
            try:
                import shutil
                shutil.copy2(filepath, export_path)
                messagebox.showinfo("Export Complete", f"Save file exported to:\n{export_path}")
            except Exception as e:
                messagebox.showerror("Export Failed", f"Failed to export save file:\n{str(e)}")
    
    def _import_save(self):
        """Import a save file"""
        from tkinter import filedialog
        
        import_path = filedialog.askopenfilename(
            title="Import Save File",
            filetypes=[("Hockey Manager Save", "*.hm"), ("All Files", "*.*")]
        )
        
        if import_path:
            try:
                import shutil
                import os
                
                # Get destination path
                filename = os.path.basename(import_path)
                dest_path = os.path.join(self.save_manager.save_directory, filename)
                
                # Check if file already exists
                if os.path.exists(dest_path):
                    result = messagebox.askyesno("File Exists", 
                                               f"A save file named '{filename}' already exists. Overwrite?")
                    if not result:
                        return
                
                shutil.copy2(import_path, dest_path)
                messagebox.showinfo("Import Complete", f"Save file imported successfully")
                self._refresh_file_list()
                
            except Exception as e:
                messagebox.showerror("Import Failed", f"Failed to import save file:\n{str(e)}")
    
    def _delete_selected_save(self):
        """Delete selected save file"""
        selection = self.file_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a save file to delete")
            return
        
        # Get selected file info
        item = selection[0]
        filename = self.file_tree.set(item, 'filename')
        filepath = self.file_tree.set(item, 'filepath')
        
        # Confirm deletion
        result = messagebox.askyesno("Confirm Delete", 
                                   f"Are you sure you want to delete '{filename}'?\n\nThis action cannot be undone.")
        
        if result:
            try:
                os.remove(filepath)
                messagebox.showinfo("Delete Complete", f"Save file '{filename}' has been deleted")
                self._refresh_file_list()
            except Exception as e:
                messagebox.showerror("Delete Failed", f"Failed to delete save file:\n{str(e)}")
    
    def _sort_files(self, column):
        """Sort files by column"""
        # Implementation for sorting the file list
        # This would sort the treeview by the selected column
        pass
    
    def _create_file_context_menu(self):
        """Create context menu for file operations"""
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Load", command=self._context_load_file)
        self.context_menu.add_command(label="Rename", command=self._context_rename_file)
        self.context_menu.add_command(label="Export", command=self._export_save)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete", command=self._delete_selected_save)
        self.context_menu.add_command(label="Properties", command=self._show_file_properties)
    
    def _show_file_context_menu(self, event):
        """Show context menu for file operations"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
    
    def _context_load_file(self):
        """Load file from context menu"""
        if hasattr(self, '_load_game'):
            self._load_game()
    
    def _context_rename_file(self):
        """Rename file from context menu"""
        selection = self.file_tree.selection()
        if not selection:
            return
        
        # Get current filename
        item = selection[0]
        current_name = self.file_tree.set(item, 'filename')
        current_path = self.file_tree.set(item, 'filepath')
        
        # Simple rename dialog
        new_name = tk.simpledialog.askstring("Rename File", 
                                           f"Enter new name for '{current_name}':",
                                           initialvalue=current_name.replace('.hm', ''))
        
        if new_name and new_name.strip():
            if not new_name.endswith('.hm'):
                new_name += '.hm'
            
            new_path = os.path.join(os.path.dirname(current_path), new_name)
            
            try:
                os.rename(current_path, new_path)
                messagebox.showinfo("Rename Complete", f"File renamed to '{new_name}'")
                self._refresh_file_list()
            except Exception as e:
                messagebox.showerror("Rename Failed", f"Failed to rename file:\n{str(e)}")
    
    def _show_file_properties(self):
        """Show detailed properties of selected file"""
        selection = self.file_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        filepath = self.file_tree.set(item, 'filepath')
        
        # Load save metadata
        try:
            save_data = self.save_manager._load_save_metadata(filepath)
            if save_data:
                self._show_save_properties_dialog(save_data, filepath)
            else:
                messagebox.showerror("Error", "Could not read save file properties")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file properties:\n{str(e)}")
    
    def _show_save_properties_dialog(self, save_data, filepath):
        """Show save file properties in a dialog"""
        # Create properties window
        props_window = tk.Toplevel(self)
        props_window.title("Save File Properties")
        props_window.geometry("500x400")
        props_window.configure(background=self.parent.BG_COLOR)
        
        # Create scrollable text widget to show properties
        text_frame = ttk.Frame(props_window, style='Content.TFrame')
        text_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        text_widget = tk.Text(text_frame, wrap='word', 
                             font=(self.parent.FONT_FAMILY, 10))
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Format properties text
        props_text = self._format_save_properties(save_data, filepath)
        text_widget.insert('1.0', props_text)
        text_widget.config(state='disabled')
        
        # Close button
        ttk.Button(props_window, text="Close", command=props_window.destroy,
                  style='TButton').pack(pady=10)
    
    def _format_save_properties(self, save_data, filepath):
        """Format save data into readable properties text"""
        lines = []
        lines.append("=== SAVE FILE PROPERTIES ===\n")
        
        # File info
        lines.append(f"File Path: {filepath}")
        
        if os.path.exists(filepath):
            stat = os.stat(filepath)
            lines.append(f"File Size: {round(stat.st_size / (1024 * 1024), 2)} MB")
            lines.append(f"Created: {datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
        
        lines.append("")
        
        # Save data info
        lines.append("=== GAME DATA ===")
        lines.append(f"Save Version: {save_data.get('version', 'Unknown')}")
        lines.append(f"Saved On: {save_data.get('timestamp', 'Unknown')}")
        lines.append(f"User Team: {save_data.get('user_team', 'Unknown')}")
        lines.append(f"Season Year: {save_data.get('season_year', 'Unknown')}")
        lines.append(f"Game Date: {save_data.get('game_date', 'Unknown')}")
        
        # Enhanced data if available
        if 'enhanced_data' in save_data:
            enhanced = save_data['enhanced_data']
            lines.append("")
            lines.append("=== SAVE DETAILS ===")
            lines.append(f"Description: {enhanced.get('description', 'None')}")
            lines.append(f"Category: {enhanced.get('category', 'General')}")
            lines.append(f"Include Stats: {enhanced.get('include_stats', True)}")
        
        return "\n".join(lines)
    
    def _on_enhanced_file_select(self, event):
        """Handle enhanced file selection"""
        if hasattr(self, 'load_btn'):
            selection = self.file_tree.selection()
            self.load_btn.config(state='normal' if selection else 'disabled')
    
    def _load_game(self):
        """Load the selected game"""
        selection = self.file_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a save file to load")
            return
        
        # Get selected file path
        item = selection[0]
        filepath = self.file_tree.set(item, 'filepath')
        filename = self.file_tree.item(item)['values'][0]
        
        # Confirm load
        result = messagebox.askyesno("Load Game", 
                                   f"Load game from '{filename}'?\n\n"
                                   f"This will replace your current game progress.")
        
        if not result:
            return
        
        # Perform load
        success = self.save_manager.load_game(filepath)
        
        if success:
            # Store loaded file path for main menu integration
            self.loaded_file_path = filepath
            # Notify parent if it has the callback
            if hasattr(self.parent, 'on_game_loaded'):
                self.parent.on_game_loaded()
            self.destroy()  # Close the load window
        else:
            messagebox.showerror("Load Failed", "Failed to load game")


def test_save_system():
    """Test the save/load system"""
    try:
        # Create a dummy game manager for testing
        class DummyGameManager:
            def __init__(self):
                from game_classes import League, Team, Player, PlayerPosition
                
                # Create test data
                self.league = League(league_name="Test League", season_year=2024)
                
                # Clear default teams and add our test team
                self.league.teams.clear()
                
                team = Team("Test Team", "Test City", "Test Division", "Test Conference")
                player = Player("Test", "Player", 25, PlayerPosition.CENTER)
                team.roster = [player]
                self.league.teams.append(team)
                
                self.user_team = team
                self.current_date = date.today()
                self.game_results = []
                self.settings = {"test_setting": True}
        
        game_manager = DummyGameManager()
        save_manager = GameSaveManager(game_manager)
        
        # Test save
        print("Testing save...")
        success = save_manager.save_game("test_save.hm")
        print(f"Save test {'passed' if success else 'failed'}")
        
        # Test load
        print("Testing load...")
        success = save_manager.load_game(os.path.join(save_manager.save_directory, "test_save.hm"))
        print(f"Load test {'passed' if success else 'failed'}")
        
        print("Save/Load system test completed!")
        
    except Exception as e:
        print(f"Save/Load system test failed: {e}")


if __name__ == "__main__":
    test_save_system()
