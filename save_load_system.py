"""
Comprehensive Save/Load System for Hockey Manager
Handles saving and loading complete game states including players, teams, leagues, and progress
"""

import pickle
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog
from popup_system import messagebox, InGamePopup, simpledialog
import customtkinter as ctk
from ctk_theme import BG
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional
import gzip
import threading
from dataclasses import asdict
import sys


def _safe_asdict(obj: Any) -> Dict[str, Any]:
    """asdict() for a dataclass, else its __dict__, else {}. Never raises."""
    try:
        if obj is None:
            return {}
        try:
            return asdict(obj)
        except Exception:
            d = getattr(obj, "__dict__", None)
            return dict(d) if isinstance(d, dict) else {}
    except Exception:
        return {}


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
                # Attribute scale stamp: saves written by the current
                # 1-100 attribute engine carry this. The legacy-scale
                # migration must never touch a stamped save (its mean
                # heuristic misfires on modern prospect pools).
                'attribute_scale': 100,
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
                # Scout region assignments (set_scout_region). Were never
                # serialized: every load unassigned all scouts.
                'scout_region_assignments': dict(
                    getattr(self.game_manager, 'scout_region_assignments', {}) or {}),
                
                # Free agency and waivers
                'free_agents': self._serialize_free_agents(),
                'waiver_claims': getattr(self.game_manager, 'waiver_claims', []),

                # Active training programs (Development Center)
                'training_programs': getattr(self.game_manager, 'training_programs', {}),
                
                # Trade and contract data
                'trade_history': getattr(self.game_manager, 'trade_history', []),
                'contract_negotiations': getattr(self.game_manager, 'contract_negotiations', {}),
                # Live trade negotiations (delayed AI answers, counters)
                'trade_negotiations': [
                    (n.to_dict() if hasattr(n, 'to_dict') else n)
                    for n in getattr(self.game_manager, 'trade_negotiations', []) or []
                ],
                # Deadline-day game clock (9 AM -> 3 PM ET, 30-min increments)
                'deadline_clock': dict(
                    getattr(self.game_manager, 'deadline_clock', None) or {}),
                
                # Email and communication
                'inbox_messages': getattr(self.game_manager, 'inbox_messages', []),
                'news_stories': getattr(self.game_manager, 'news_stories', []),

                # League Memory: season archive, Hall of Fame
                'league_history': (
                    self.game_manager.league_history.to_dict()
                    if getattr(self.game_manager, 'league_history', None) else {}
                ),

                # Narrative ledger: rivalry + series memory (normalized events).
                # Resolve the canonical ledger -- it is lazily attached to
                # the GUI app via get_ledger(app), while this manager wraps
                # the inner GameManager; reading only the wrapped manager
                # silently saved {} and wiped history on load.
                'narrative_ledger': self._canonical_ledger_dict(),

                # Shot charts: replayable evidence (last 50 games)
                'shot_charts': (
                    self.game_manager.shot_chart_store.to_dict()
                    if getattr(self.game_manager, 'shot_chart_store', None) else {}
                ),

                # Coaching carousel: fired/available coaches (module 03).
                # Entries hold live coach objects, pickled like
                # coaching_staff below. Missing key = old save -> empty.
                'coach_carousel': self._serialize_coach_carousel(),
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
    
    def _canonical_ledger(self):
        """Return the live narrative ledger, wherever it is attached.

        The ledger is lazily attached to the GUI app via get_ledger(app),
        but the save manager wraps the inner GameManager -- so resolve in
        order: app-attached (the live one during play), the module-global
        active ledger, then the wrapped manager's attribute.
        """
        gm = self.game_manager
        try:
            app = getattr(gm, 'app', None)
            led = getattr(app, 'narrative_ledger', None)
            if led is not None:
                return led
        except Exception:
            pass
        try:
            from narrative_ledger import active_ledger
            led = active_ledger()
            if led is not None:
                return led
        except Exception:
            pass
        return getattr(gm, 'narrative_ledger', None)

    def _canonical_ledger_dict(self):
        try:
            led = self._canonical_ledger()
            return led.to_dict() if led is not None else {}
        except Exception:
            return {}

    def _restore_canonical_ledger(self, ledger):
        """Stamp a restored ledger everywhere the game reads it from."""
        try:
            from narrative_ledger import set_active_ledger
            set_active_ledger(ledger)
        except Exception:
            pass
        try:
            self.game_manager.narrative_ledger = ledger
        except Exception:
            pass
        try:
            app = getattr(self.game_manager, 'app', None)
            if app is not None:
                app.narrative_ledger = ledger
        except Exception:
            pass

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
            # Legacy events: permanent outdoor-game memory (plain dicts).
            'outdoor_history': list(getattr(league, 'outdoor_history', []) or []),
            # All-Star rosters by season label (plain ID dicts). Missing
            # key = old save -> empty, selection runs fresh that season.
            'all_star_rosters': {str(k): dict(v) for k, v in
                                 (getattr(league, 'all_star_rosters', None) or {}).items()},
            # Rivalries & bad blood (plain dicts): brawl heat, playoff feuds,
            # declared rivalries -- "so bad blood follows people". Was never
            # serialized; every save wiped it. Missing key = old save.
            'rivalries': [dict(r) for r in
                          (getattr(league, 'rivalries', None) or [])],
            'lottery_results': {int(k): [dict(r) for r in v]
                                for k, v in
                                (getattr(league, 'lottery_results', None) or {}).items()},
            'lottery_held_years': sorted(getattr(league, 'lottery_held_years', None) or []),
            'intl_held': {k: sorted(v) for k, v in
                          (getattr(league, 'intl_held', None) or {}).items()},
            'intl_history': [dict(h) for h in
                             (getattr(league, 'intl_history', None) or [])],
            'intl_prep': {str(k): v for k, v in
                          (getattr(league, 'intl_prep', None) or {}).items()},
            'intl_announced': sorted(
                getattr(league, 'intl_announced', None) or []),
            'draft_held_years': list(getattr(league, 'draft_held_years', []) or []),
            # Years the draft was actually conducted (idempotency guard).
            # Missing key = old save -> empty list.
            'draft_conducted_years': sorted(
                getattr(league, 'draft_conducted_years', None) or []),
            # Draft grades history {str(year): [(team, grade, ratio)]}.
            # Missing key = old save -> empty dict.
            'draft_grades_history': {
                str(k): [[t, g, float(r)] for t, g, r in (v or [])]
                for k, v in (getattr(league, 'draft_grades_history', None)
                             or {}).items()},
            # Prospect awards news + prospect-class year stamp (his draft
            # wave). Missing keys = old save -> graceful defaults.
            'prospect_awards_news': list(getattr(league, 'prospect_awards_news', []) or []),
            # ELC slide headlines from the offseason rollover (CBA 9.1(d)).
            # Missing key = old save -> empty news.
            'elc_slide_news': list(getattr(league, 'elc_slide_news', []) or []),
            # Rivalry-review verdicts from the triennial offseason review.
            # Missing key = old save -> empty news.
            'rivalry_review_news': list(getattr(league, 'rivalry_review_news', []) or []),
            # Staff breakthrough headlines from the offseason rollover.
            # Missing key = old save -> empty news.
            'staff_breakthrough_news': list(getattr(league, 'staff_breakthrough_news', []) or []),
            'draft_prospects_year': getattr(league, 'draft_prospects_year', None),
            # Draft class + staff pools. These were never serialized: every
            # save/load wiped the draft class (scouting wasted; the draft
            # regenerated a different class), all team coaches/scouts, and
            # the staff hiring pool. Missing keys = old save -> [].
            'draft_prospects': [self._serialize_player(p)
                                for p in (getattr(league, 'draft_prospects', None) or [])],
            'free_agent_staff': [self._serialize_staff(s)
                                 for s in (getattr(league, 'free_agent_staff', None) or [])],
            # Overseas coaching talent. Absent in old saves -> [].
            'overseas_staff': [self._serialize_staff(s)
                               for s in (getattr(league, 'overseas_staff', None) or [])],
            'event_day_prompted': [list(p) for p in (getattr(league, 'event_day_prompted', []) or [])],
            # Dynamic salary cap system (growth history + market comps).
            # Missing key = old save -> defaults to the modern $104M cap.
            'salary_cap_system': getattr(league, 'salary_cap_system', None).to_dict()
                if getattr(league, 'salary_cap_system', None) else {},
            # Live playoff bracket (mid-tournament saves keep every game).
            # Missing key = old save -> no bracket, projections shown.
            'playoff_bracket': self._serialize_playoff_bracket(league),
            # Immortality: retired-player snapshots (HOF ballot arcs live
            # here). Was never serialized -- every save deleted them from
            # the universe. Missing key = old save -> empty.
            'retired_players': [dict(r) for r in
                                (getattr(league, 'retired_players', None) or [])],
            # Milestone idempotency: which (player, milestone) pairs already
            # got their ceremony. Without this, a load re-fires every past
            # milestone. Missing key = old save -> rebuilt from scratch.
            '_milestone_celebrated': [list(k) for k in
                                     (getattr(league, '_milestone_celebrated', None) or set())],
            # Draft-steal retrospective idempotency: which players already
            # got their steal story. Same bug class as milestones -- a load
            # re-fires every past retrospective without this.
            # Missing key = old save -> rebuilt from scratch.
            'steal_retro_posted': list(getattr(league, 'steal_retro_posted', None) or set()),
            # Copycat-league dynasty tracking: defending-champ identity +
            # the core systems that won. The AI GM defending-champ leash
            # and dynasty-blueprint heat read these; without them a load
            # resets both. Missing keys = old save -> fresh tracking.
            '_last_cup_champ': getattr(league, '_last_cup_champ', None),
            '_last_champ_core': sorted(getattr(league, '_last_champ_core', None) or []),
            '_blueprint_dynasties': dict(getattr(league, '_blueprint_dynasties', None) or {}),
            # Media story state: ongoing narratives, coach-vs-reporter
            # beefs, fines. Stored as plain dicts (objects rebuilt on
            # restore). Without these, media arcs vanish mid-story on load.
            # Missing keys = old save -> no active stories.
            'media_narratives': [dict(getattr(n, '__dict__', None) or {})
                                 for n in (getattr(league, 'media_narratives', None) or [])],
            'coach_media_beefs': [dict(getattr(b, '__dict__', None) or {})
                                  for b in (getattr(league, 'coach_media_beefs', None) or [])],
            'media_fines': [dict(f) for f in
                            (getattr(league, 'media_fines', None) or [])],
            # Draft Day Central deals feed (summaries). Missing = old save.
            'draft_day_deals': list(getattr(league, 'draft_day_deals', None) or []),
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
                # Team staff (coaches, scouts, development). Was never
                # serialized: every load wiped every club's staff.
                'staff': [self._serialize_staff(s)
                          for s in (getattr(team, 'staff', None) or [])],
                # Annual staff payroll budget (league-wide rule, market-tiered).
                # Absent in old saves -> tier default by club name.
                'staff_budget': int(getattr(team, 'staff_budget', 0) or 0),
                'stats': self._serialize_team_stats(getattr(team, 'stats', None)),
                'salary_cap_info': getattr(team, 'salary_cap_info', {}),
                'draft_picks': getattr(team, 'draft_picks', {}),
                'trade_block': getattr(team, 'trade_block', []),
                'division': getattr(team, 'division', ''),
                'conference': getattr(team, 'conference', ''),
                # League identity (NHL vs AHL). Was never serialized: every
                # load reset all 62 clubs to the dataclass default
                # ("National Hockey League"), which broke the draft lottery
                # and draft order's NHL filters on any loaded career.
                'league_name': getattr(team, 'league_name', 'National Hockey League'),
                'standings_position': getattr(team, 'standings_position', 0),
                'board_expectation': getattr(team, 'board_expectation', None),
                'buyout_cap_hits': dict(getattr(team, 'buyout_cap_hits', {}) or {}),
                # In-game retained-salary ledger (real NHL retained
                # transactions). Absent in old saves -> empty.
                'retained_salary': [dict(e) for e in
                                    (getattr(team, 'retained_salary', None) or [])],
                # Seeded real-life 2026-27 dead-cap penalties (0/absent on
                # old saves and when "start without cap penalties").
                'real_buyout_cap': int(getattr(team, 'real_buyout_cap', 0) or 0),
                'real_retained_salary': int(getattr(team, 'real_retained_salary', 0) or 0),
                'real_bonus_overage': int(getattr(team, 'real_bonus_overage', 0) or 0),
                'real_dead_cap_seeded': bool(getattr(team, 'real_dead_cap_seeded', False)),
                # Inbox (headlines, saved emails): must cross save/load and
                # multiplayer snapshots so every manager keeps their mail.
                'inbox': [m.to_dict() for m in
                          getattr(getattr(team, 'inbox', None), 'messages', []) or []],
                # Per-line matchup preferences from the lines screen.
                'line_matchups': {
                    'F': list((getattr(team, 'line_matchups', None) or {}).get('F') or [None] * 4)[:4],
                    'D': list((getattr(team, 'line_matchups', None) or {}).get('D') or [None] * 3)[:3],
                },
                # Retired numbers in the rafters. Was never serialized --
                # loads re-issued them to rookies. Missing = old save.
                'retired_numbers': [dict(r) for r in
                                    (getattr(team, 'retired_numbers', None) or [])],
                # Queued pregame ceremony (jersey retirement / HOF night).
                # Dropped on load before; the electric building never
                # happened. Missing = old save -> none pending.
                '_pending_ceremony': (dict(getattr(team, '_pending_ceremony'))
                                      if isinstance(getattr(team, '_pending_ceremony', None), dict)
                                      else None),
                # Iconic games: the franchise's remembered nights. Plain
                # dicts, capped at 30 by the writer. The per-team
                # "starred" flag is what survives seasons -- unstarred
                # entries are pruned at rollover. Missing = old save.
                'iconic_games': [dict(e) for e in
                                 (getattr(team, 'iconic_games', None) or [])
                                 if isinstance(e, dict)][:30],
                # Team dynamics feed (the Morale screen story). Capped at
                # 100 by the writer; the code promises it survives saves.
                # Missing = old save -> empty feed.
                'dynamics_log': [dict(e) for e in
                                 (getattr(team, 'dynamics_log', None) or [])][-100:],
                # Dressing-room story state: mood lines, pending talks,
                # arrival tracking. Missing = old save -> fresh room.
                'dressing_room': {
                    k: (list(v) if isinstance(v, list)
                        else (dict(v) if isinstance(v, dict) else v))
                    for k, v in (getattr(team, 'dressing_room', None) or {}).items()
                },
                # Pro-scout storyline state: steal/sell watches + filed tips
                # awaiting grading. Keys are player ids (pickle preserves
                # them); values are plain dicts. Missing = old save.
                'scout_watches': {
                    w: {k: dict(v) for k, v in
                        (getattr(team, w, None) or {}).items()}
                    for w in ('steal_watch', 'sell_watch', 'scout_buy_tips',
                              'scout_sell_tips', 'tip_ledger')
                },
                # Standing line-control decision (coach vs GM). Missing =
                # old save -> 'coach', matching the dataclass default.
                'line_control': getattr(team, 'line_control', 'coach') or 'coach',
                # Tactics choices + earned familiarity + saved preferences.
                # Missing = old save -> defaults, same as a fresh club.
                'tactics': {
                    'even_strength': getattr(team, 'tactic_even_strength', 'Balanced'),
                    'power_play': getattr(team, 'tactic_power_play', 'Offensive'),
                    'penalty_kill': getattr(team, 'tactic_penalty_kill', 'Defensive'),
                    'line_matching': getattr(team, 'tactic_line_matching', 'Standard'),
                    'forecheck': getattr(team, 'tactic_forecheck', '2-1-2'),
                    'offense': getattr(team, 'tactic_offense', 'Spread'),
                    'familiarity': float(getattr(team, 'tactics_familiarity', 85) or 85),
                    'installed_by': getattr(team, 'tactics_installed_by', None),
                    'preferred': dict(getattr(team, 'preferred_tactics', None) or {}),
                },
                # Parity-engine form/streak state. Missing = old save.
                '_parity_state': dict(getattr(team, '_parity_state', None) or {}),
                # Analytics-GM identity: department quality, philosophy,
                # baseline, last GM name (detects front-office changes).
                'analytics_identity': {
                    'quality': int(getattr(team, 'analytics_quality', 35) or 0),
                    'philosophy': float(getattr(team, 'analytics_philosophy', 30.0) or 0.0),
                    'baseline': float(getattr(team, 'philosophy_baseline', 30.0) or 0.0),
                    'prev_gm_name': getattr(team, '_prev_gm_name', '') or '',
                },
                # Analytics-hub snapshots (capped at 10 by the writer).
                'analytics_games': [dict(r) for r in
                                    (getattr(team, 'analytics_games', None) or [])][-10:],
                # GM name + profile. Missing = old save -> defaults.
                'gm_name': getattr(team, 'gm_name', 'General Manager') or 'General Manager',
                'gm_profile': _safe_asdict(getattr(team, 'gm_profile', None)),
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
                    elif key == 'playoff_stats' and value:
                        # Playoff ledger: same shape as stats
                        player_data[key] = self._serialize_player_stats(value)
                    elif key == 'ahl_stats' and value:
                        # AHL ledger: same shape as stats, never mixed w/ NHL
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
    
    def _serialize_staff(self, staff) -> Dict[str, Any]:
        """Serialize a Staff member (generic __dict__ walk; enums by name)."""
        try:
            if hasattr(staff, '__dict__'):
                data = {}
                for key, value in staff.__dict__.items():
                    if isinstance(value, (date, datetime)):
                        data[key] = value.isoformat()
                    elif hasattr(value, 'name'):  # Enum (StaffRole) handling
                        data[key] = value.name
                    else:
                        data[key] = value
                return data
            return {}
        except Exception as e:
            print(f"Error serializing staff: {e}")
            return {}

    def _restore_staff(self, staff_data: Dict[str, Any]):
        """Restore a Staff member from save data."""
        try:
            from game_classes import Staff, StaffRole
            if not staff_data:
                return None
            role = staff_data.get('role')
            try:
                role = StaffRole[role] if isinstance(role, str) else role
            except Exception:
                role = StaffRole.HEAD_COACH
            if role is None:
                role = StaffRole.HEAD_COACH
            staff = Staff(
                staff_data.get('first_name', ''),
                staff_data.get('last_name', ''),
                role,
            )
            for key, value in staff_data.items():
                if key in ('first_name', 'last_name', 'role'):
                    continue
                setattr(staff, key, value)
            return staff
        except Exception as e:
            print(f"Error restoring staff: {e}")
            return None

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
                        # Legacy events: the outdoor-game stamp rides along
                        # (plain dicts -- JSON/pickle safe).
                        'outdoor': game.get('outdoor') if isinstance(game, dict) else None,
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
    
    def _serialize_coach_carousel(self) -> list:
        """Serialize the coaching carousel (module 03, Wave 2).

        Entries hold live coach objects; pickle carries them the same way
        it carries team coaching_staff. Old saves simply lack the key.
        """
        try:
            import dressing_room as _dr
            return [dict(e) for e in (getattr(_dr, "COACH_CAROUSEL", []) or [])]
        except Exception as e:
            print(f"Error serializing coach carousel: {e}")
            return []

    def _restore_coach_carousel(self, entries) -> None:
        """Restore the coaching carousel into the live module list."""
        try:
            import dressing_room as _dr
            _dr.COACH_CAROUSEL[:] = list(entries or [])
        except Exception as e:
            print(f"coach carousel restore failed (non-fatal): {e}")

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
                try:
                    messagebox.showinfo("Load Complete", "Game loaded successfully!")
                except Exception:
                    pass  # headless / no display: the print above suffices

                # Re-sync mirrors. _restore_game_state rebuilds league teams
                # as NEW objects on the wrapped manager, so any other holder
                # of the old objects goes stale:
                #  - wrapper is the GUI app (SaveLoadView path): the inner
                #    GameManager keeps the pre-load user_team/current_date.
                #  - wrapper is the GameManager (direct path): a GUI app
                #    built on it keeps the pre-load mirrors. Without this,
                #    identity checks (game-day bundle lookup, schedule scans)
                #    compare against ghosts and the date desyncs.
                try:
                    _mgr = self.game_manager
                    _inner = getattr(_mgr, 'game_manager', None)
                    _true_gm = (_inner if (_inner is not None
                                           and _inner is not _mgr)
                                else _mgr)
                    if _true_gm is not _mgr:
                        for _attr in ('user_team', 'league', 'current_date'):
                            _v = getattr(_mgr, _attr, None)
                            if _v is not None:
                                try:
                                    setattr(_true_gm, _attr, _v)
                                except Exception:
                                    pass
                    _app = getattr(_true_gm, 'app', None)
                    if _app is not None and _app is not _mgr:
                        for _attr in ('league', 'user_team', 'current_date'):
                            _v = getattr(_true_gm, _attr, None)
                            if _v is not None:
                                try:
                                    setattr(_app, _attr, _v)
                                except Exception:
                                    pass
                except Exception as _se:
                    print(f"Mirror re-sync skipped (non-fatal): {_se}")

                # Update UI if available
                if hasattr(self.game_manager, 'update_all_views'):
                    self.game_manager.update_all_views()

                return True
            else:
                try:
                    messagebox.showerror("Load Error", "Failed to restore game state")
                except Exception:
                    pass
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
            # Live trade negotiations come back as dataclasses, not dicts
            if 'trade_negotiations' in save_data:
                try:
                    import trade_negotiation as _tn
                    _tn.load_state(self, save_data['trade_negotiations'])
                except Exception as _tne:
                    print(f"trade negotiations restore failed (non-fatal): {_tne}")

            # Deadline-day game clock
            if 'deadline_clock' in save_data:
                try:
                    dc = save_data['deadline_clock'] or {}
                    self.game_manager.deadline_clock = dict(dc)
                except Exception as _dce:
                    print(f"deadline clock restore failed (non-fatal): {_dce}")

            # Coaching carousel (module 03): old saves lack the key and
            # come back with an empty carousel. Always restore (even when
            # the key is missing) so a previously loaded game's carousel
            # can never leak into this one.
            self._restore_coach_carousel(save_data.get('coach_carousel', []))

            # League Memory: season archive + Hall of Fame
            if 'league_history' in save_data:
                try:
                    from league_history import LeagueHistory
                    lh_data = save_data['league_history'] or {}
                    if lh_data:
                        self.game_manager.league_history = LeagueHistory.from_dict(lh_data)
                    else:
                        self.game_manager.league_history = LeagueHistory()
                except Exception as _lhe:
                    print(f"league history restore failed (non-fatal): {_lhe}")
                    self.game_manager.league_history = None

            # Narrative ledger: rivalry + series memory (old saves backfill
            # empty — history is never invented, per the integrity rules).
            # Restored onto every owner: the wrapped manager, the GUI app
            # (the live ledger during play), and the module-global active
            # ledger -- otherwise the app kept reading its own stale object.
            if 'narrative_ledger' in save_data:
                try:
                    from narrative_ledger import NarrativeLedger
                    nl_data = save_data['narrative_ledger'] or {}
                    if nl_data:
                        restored = NarrativeLedger.from_dict(nl_data)
                    else:
                        restored = NarrativeLedger()
                    self._restore_canonical_ledger(restored)
                except Exception as _nle:
                    print(f"narrative ledger restore failed (non-fatal): {_nle}")
                    try:
                        self._restore_canonical_ledger(NarrativeLedger())
                    except Exception:
                        pass

            # Shot charts: replayable evidence
            if 'shot_charts' in save_data:
                try:
                    from shot_charts import ShotChartStore
                    sc_data = save_data['shot_charts'] or {}
                    if sc_data:
                        self.game_manager.shot_chart_store = ShotChartStore.from_dict(sc_data)
                    else:
                        self.game_manager.shot_chart_store = ShotChartStore()
                except Exception as _sce:
                    print(f"shot charts restore failed (non-fatal): {_sce}")
                    self.game_manager.shot_chart_store = None

            for key in ['player_stats_history', 'team_stats_history', 'draft_classes',
                       'scouting_reports', 'scout_region_assignments', 'waiver_claims', 'trade_history',
                       'contract_negotiations', 'inbox_messages', 'news_stories',
                       'training_programs']:
                if key in save_data:
                    setattr(self.game_manager, key, save_data[key])

            # Re-mirror restored training programs into the Development
            # Center's module registry so the window shows them.
            if getattr(self.game_manager, 'training_programs', None):
                try:
                    from enhanced_practice_system import ACTIVE_TRAINING_PROGRAMS
                    for pid, prog in self.game_manager.training_programs.items():
                        ACTIVE_TRAINING_PROGRAMS[pid] = prog
                except Exception:
                    pass

            # Restore FM-style career state
            if save_data.get('career_data'):
                try:
                    from manager_career import CareerState
                    target = self.game_manager
                    # Career state lives on the GameManager, but the save
                    # manager may wrap the GUI app (SaveLoadView path) whose
                    # `career` is a read-only property — assigning to it
                    # raises AttributeError and silently drops the career.
                    # Unwrap to the inner GameManager first.
                    inner = getattr(target, 'game_manager', None)
                    if inner is not None and inner is not target:
                        target = inner
                    target.career = CareerState.from_dict(save_data['career_data'])
                except Exception as e:
                    print(f"Could not restore career data: {e}")
            
            # Restore free agents
            if 'free_agents' in save_data:
                self._restore_free_agents(save_data['free_agents'])

            # One-time migration: saves written before the 1-100 scale audit
            # store player attributes on the legacy ~50 scale. Detect by
            # league-wide attribute mean (legacy ~35, current ~72) and double
            # the 100-scale fields. Saves stamped attribute_scale >= 100
            # (i.e. written by the current engine) are never touched — the
            # mean heuristic misfires on modern prospect pools.
            try:
                self._migrate_legacy_attribute_scale(
                    save_data.get('attribute_scale'))
            except Exception as e:
                print(f"Legacy scale migration skipped: {e}")

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
            # BUG-018: re-anchor the draft-pick value/expiry clock to the
            # save's season. The anchor is process-global, set only at
            # league creation and end_of_season -- without this, every
            # loaded career values picks against the real-world year and
            # BUG-016's expired-pick guards silently don't apply.
            try:
                from game_classes import set_pick_value_anchor_year
                set_pick_value_anchor_year(league.season_year)
            except Exception:
                pass
            league.standings = league_data.get('standings', {})
            league.schedule_generated = league_data.get('schedule_generated', False)
            league.outdoor_history = list(league_data.get('outdoor_history', []) or [])
            league.all_star_rosters = {str(k): dict(v) for k, v in
                                       (league_data.get('all_star_rosters', None) or {}).items()}
            league.rivalries = [dict(r) for r in
                                (league_data.get('rivalries', None) or [])]
            # Immortality restores: retired-player snapshots (HOF ballot
            # arcs) and the milestone idempotency set. Absent in old
            # saves -> empty, same as a fresh league.
            league.retired_players = [dict(r) for r in
                                      (league_data.get('retired_players', None) or [])]
            try:
                league._milestone_celebrated = set(
                    tuple(k) for k in
                    (league_data.get('_milestone_celebrated', None) or []))
            except Exception:
                league._milestone_celebrated = set()
            # Draft-steal retrospective idempotency. Absent in old
            # saves -> empty, same as a fresh league.
            try:
                league.steal_retro_posted = set(
                    league_data.get('steal_retro_posted', None) or [])
            except Exception:
                league.steal_retro_posted = set()
            # Copycat-league dynasty tracking. Absent in old saves ->
            # no defending champ, no dynasty runs -- same as fresh.
            league._last_cup_champ = league_data.get('_last_cup_champ', None)
            try:
                league._last_champ_core = frozenset(
                    league_data.get('_last_champ_core', None) or [])
            except Exception:
                league._last_champ_core = frozenset()
            try:
                league._blueprint_dynasties = dict(
                    league_data.get('_blueprint_dynasties', None) or {})
            except Exception:
                league._blueprint_dynasties = {}
            # Media story state: rebuild Narrative / CoachMediaBeef
            # objects from their plain-dict snapshots; fines are
            # already dicts. Absent in old saves -> no active stories.
            try:
                from media_engine import Narrative, CoachMediaBeef
                _narrs = []
                for _nd in (league_data.get('media_narratives', None) or []):
                    try:
                        _n = Narrative.__new__(Narrative)
                        _n.__dict__.update(dict(_nd))
                        _narrs.append(_n)
                    except Exception:
                        continue
                league.media_narratives = _narrs
                _beefs = []
                for _bd in (league_data.get('coach_media_beefs', None) or []):
                    try:
                        _b = CoachMediaBeef.__new__(CoachMediaBeef)
                        _b.__dict__.update(dict(_bd))
                        _beefs.append(_b)
                    except Exception:
                        continue
                league.coach_media_beefs = _beefs
            except Exception:
                league.media_narratives = []
                league.coach_media_beefs = []
            league.media_fines = [dict(f) for f in
                                  (league_data.get('media_fines', None) or [])]
            league.draft_day_deals = list(
                league_data.get('draft_day_deals', None) or [])
            try:
                league.lottery_results = {
                    int(k): [dict(r) for r in v]
                    for k, v in (league_data.get('lottery_results', None) or {}).items()
                }
            except Exception:
                league.lottery_results = {}
            league.lottery_held_years = sorted(
                league_data.get('lottery_held_years', None) or [])
            try:
                league.intl_held = {
                    str(k): sorted(v) for k, v in
                    (league_data.get('intl_held', None) or {}).items()
                }
                if "olympics" not in league.intl_held:
                    league.intl_held["olympics"] = []
                if "worlds" not in league.intl_held:
                    league.intl_held["worlds"] = []
            except Exception:
                league.intl_held = {"olympics": [], "worlds": []}
            league.intl_history = [dict(h) for h in
                                   (league_data.get('intl_history', None) or [])]
            try:
                league.intl_prep = {
                    int(k): v for k, v in
                    (league_data.get('intl_prep', None) or {}).items()
                }
            except Exception:
                league.intl_prep = {}
            league.intl_announced = sorted(
                league_data.get('intl_announced', None) or [])
            # Tentpole event state (years the entry draft was held, event
            # prompts already shown). Defaults keep old saves working.
            league.draft_held_years = list(league_data.get('draft_held_years', []) or [])
            # Years the draft's picks were actually conducted (idempotency
            # guard for the headless conductor / war room). Old saves lack
            # the key -> empty list (nothing was stamped yet).
            league.draft_conducted_years = sorted(
                league_data.get('draft_conducted_years', None) or [])
            # Draft grades history {str(year): [(team, grade, ratio)]}.
            # Old saves lack the key -> empty dict.
            try:
                _dgh = league_data.get('draft_grades_history', None) or {}
                league.draft_grades_history = {
                    str(k): [(t, g, float(r)) for t, g, r in (v or [])]
                    for k, v in _dgh.items()}
            except Exception:
                league.draft_grades_history = {}
            # Prospect awards news + prospect-class year stamp (his draft
            # wave). Old saves lack the keys -> empty news, None year (his
            # draft flow regenerates the class when the stamp mismatches).
            league.prospect_awards_news = list(
                league_data.get('prospect_awards_news', []) or [])
            # ELC slide headlines. Old saves lack the key -> empty news.
            league.elc_slide_news = list(
                league_data.get('elc_slide_news', []) or [])
            # Rivalry-review verdicts. Old saves lack the key -> empty news.
            league.rivalry_review_news = list(
                league_data.get('rivalry_review_news', []) or [])
            # Staff breakthrough headlines. Old saves lack the key ->
            # empty news.
            league.staff_breakthrough_news = list(
                league_data.get('staff_breakthrough_news', []) or [])
            league.draft_prospects_year = league_data.get('draft_prospects_year', None)
            # Draft class + staff pools (see serialize side). Old saves lack
            # the keys -> empty lists (draft regenerates its class at draft
            # time when empty; staff stays empty for old saves).
            try:
                league.draft_prospects = [
                    p for p in (self._restore_player(d)
                                for d in (league_data.get('draft_prospects', None) or []))
                    if p is not None]
            except Exception:
                league.draft_prospects = []
            try:
                league.free_agent_staff = [
                    s for s in (self._restore_staff(d)
                                for d in (league_data.get('free_agent_staff', None) or []))
                    if s is not None]
            except Exception:
                league.free_agent_staff = []
            try:
                league.overseas_staff = [
                    s for s in (self._restore_staff(d)
                                for d in (league_data.get('overseas_staff', None) or []))
                    if s is not None]
            except Exception:
                league.overseas_staff = []
            league.event_day_prompted = [
                list(p) for p in (league_data.get('event_day_prompted', []) or [])
            ]
            # Restore salary cap system. Old saves lack the key -> defaults
            # to the modern $104M cap with empty history (no crash, no data loss).
            try:
                from salary_cap_system import SalaryCapSystem
                league.salary_cap_system = SalaryCapSystem.from_dict(
                    league_data.get('salary_cap_system') or {})
                # Sync team caps to the restored league cap
                _restored_cap = league.salary_cap_system.current_cap
                for _t in league.teams:
                    if not getattr(_t, 'salary_cap', 0):
                        _t.salary_cap = _restored_cap
            except Exception:
                pass
            
            # Restore teams (clear existing and restore from save)
            league.teams.clear()
            teams_data = league_data.get('teams', [])
            
            for team_data in teams_data:
                team = self._restore_team(team_data)
                if team:
                    league.teams.append(team)

            # Restore a live playoff bracket (mid-tournament save). Teams
            # now exist again, so series can re-point at them by name.
            try:
                self._restore_playoff_bracket(
                    league, league_data.get('playoff_bracket'))
            except Exception:
                pass
            
        except Exception as e:
            print(f"Error restoring league: {e}")

    def _serialize_playoff_bracket(self, league):
        """Serialize the live playoff bracket (plain dicts; None when idle)."""
        try:
            b = getattr(league, 'playoff_bracket', None)
            if b is None or not getattr(b, 'playoff_series', None):
                return None
            if not any(b.playoff_series.get(r)
                       for r in ('wild_card', 'division_semifinals',
                                 'division_finals', 'conference_finals',
                                 'stanley_cup_final')):
                return None
            champ = getattr(b, 'stanley_cup_champion', None)
            return {
                'current_round': getattr(b, 'current_round', 'wild_card'),
                'is_projection': bool(getattr(b, 'is_projection', False)),
                'champion': getattr(champ, 'team_name', None),
                'eastern': [getattr(t, 'team_name', '')
                            for t in getattr(b, 'eastern_teams', None) or []],
                'western': [getattr(t, 'team_name', '')
                            for t in getattr(b, 'western_teams', None) or []],
                'series': [
                    {'round': rkey,
                     'round_name': getattr(s, 'round_name', ''),
                     'team1': getattr(s.team1, 'team_name', ''),
                     'team2': getattr(s.team2, 'team_name', ''),
                     't1_wins': int(getattr(s, 'team1_wins', 0) or 0),
                     't2_wins': int(getattr(s, 'team2_wins', 0) or 0),
                     'games_played': int(getattr(s, 'games_played', 0) or 0),
                     'is_complete': bool(getattr(s, 'is_complete', False)),
                     'winner': getattr(getattr(s, 'winner', None),
                                       'team_name', None),
                     'game_results': [dict(g) for g in
                                      getattr(s, 'game_results', None) or []]}
                    for rkey, slist in b.playoff_series.items()
                    for s in slist or []
                ],
            }
        except Exception:
            return None

    def _restore_playoff_bracket(self, league, data):
        """Rebuild the live playoff bracket from plain dicts."""
        if not data:
            return
        try:
            from playoff_system import PlayoffBracket, PlayoffSeries
            by_name = {getattr(t, 'team_name', ''): t
                       for t in getattr(league, 'teams', None) or []}
            b = PlayoffBracket(league)
            b.current_round = data.get('current_round', 'wild_card')
            b.is_projection = bool(data.get('is_projection', False))
            for name in data.get('eastern', None) or []:
                if name in by_name:
                    b.eastern_teams.append(by_name[name])
            for name in data.get('western', None) or []:
                if name in by_name:
                    b.western_teams.append(by_name[name])
            for i, t in enumerate(b.eastern_teams):
                t.standings_position = i + 1
            for i, t in enumerate(b.western_teams):
                t.standings_position = i + 1
            for sd in data.get('series', None) or []:
                t1 = by_name.get(sd.get('team1', ''))
                t2 = by_name.get(sd.get('team2', ''))
                if t1 is None or t2 is None:
                    continue
                s = PlayoffSeries(sd.get('round_name', ''), t1, t2)
                s.team1_wins = int(sd.get('t1_wins', 0) or 0)
                s.team2_wins = int(sd.get('t2_wins', 0) or 0)
                s.games_played = int(sd.get('games_played', 0) or 0)
                s.is_complete = bool(sd.get('is_complete', False))
                wname = sd.get('winner')
                s.winner = by_name.get(wname) if wname else None
                s.game_results = [dict(g) for g in
                                  sd.get('game_results', None) or []]
                rkey = sd.get('round', '')
                if rkey in b.playoff_series:
                    b.playoff_series[rkey].append(s)
            cname = data.get('champion')
            b.stanley_cup_champion = by_name.get(cname) if cname else None
            league.playoff_bracket = b
        except Exception:
            pass
    
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
            # League identity (NHL vs AHL). Old saves lack the key: infer
            # from division -- farm clubs have division "Unknown" (the same
            # discriminator the standings/snapshot code uses). Without this,
            # pre-fix saves load all 62 clubs as NHL and downstream filters
            # (schedule generator's 32-team check, draft lottery) admit AHL
            # clubs. BUG-014 follow-up.
            if 'league_name' in team_data:
                team.league_name = team_data['league_name']
            elif team_data.get('division', '') == 'Unknown':
                team.league_name = 'American Hockey League'
            else:
                team.league_name = getattr(team, 'league_name',
                                           'National Hockey League')
            # Self-heal: saves re-saved while corrupted (all 62 stamped NHL
            # by the pre-fix default) carry the wrong explicit value. Farm
            # clubs are the ones with division "Unknown" -- never a real
            # NHL club -- so stamp them back to the AHL unconditionally.
            if team_data.get('division', '') == 'Unknown' and \
                    team.league_name == 'National Hockey League':
                team.league_name = 'American Hockey League'
            team.standings_position = team_data.get('standings_position', 0)
            team.coaching_staff = team_data.get('coaching_staff', [])
            # Team staff (coaches/scouts). Old saves lack the key -> empty.
            try:
                team.staff = [
                    s for s in (self._restore_staff(d)
                                for d in (team_data.get('staff', None) or []))
                    if s is not None]
            except Exception:
                team.staff = []
            team.salary_cap_info = team_data.get('salary_cap_info', {})
            team.draft_picks = team_data.get('draft_picks', {})
            team.trade_block = team_data.get('trade_block', [])
            team.board_expectation = team_data.get('board_expectation')
            # Annual staff payroll budget. Absent in old saves -> market-tier
            # default so existing leagues get the rule without a wipe.
            try:
                from game_classes import default_staff_budget as _dsb
                team.staff_budget = int(team_data.get('staff_budget') or _dsb(
                    team_data.get('team_name', '')))
            except Exception:
                team.staff_budget = 10_000_000
            team.buyout_cap_hits = dict(team_data.get('buyout_cap_hits', {}) or {})
            # Retained-salary ledger. Absent in old saves -> empty.
            team.retained_salary = [dict(e) for e in
                                    (team_data.get('retained_salary', None) or [])]
            # Seeded real-life dead-cap penalties. Absent in old saves -> 0.
            team.real_buyout_cap = int(team_data.get('real_buyout_cap', 0) or 0)
            team.real_retained_salary = int(team_data.get('real_retained_salary', 0) or 0)
            team.real_bonus_overage = int(team_data.get('real_bonus_overage', 0) or 0)
            team.real_dead_cap_seeded = bool(team_data.get('real_dead_cap_seeded', False))
            # Line matchup preferences. Absent in old saves -> all Auto.
            _lm = team_data.get('line_matchups') or {}
            _lmf = list(_lm.get('F') or [None] * 4)[:4]
            _lmd = list(_lm.get('D') or [None] * 3)[:3]
            team.line_matchups = {
                'F': _lmf + [None] * (4 - len(_lmf)),
                'D': _lmd + [None] * (3 - len(_lmd)),
            }
            # Retired numbers in the rafters + any queued pregame ceremony.
            # Absent in old saves -> empty / none, same as a fresh club.
            team.retired_numbers = [dict(r) for r in
                                    (team_data.get('retired_numbers', None) or [])]
            _pc = team_data.get('_pending_ceremony', None)
            team._pending_ceremony = dict(_pc) if isinstance(_pc, dict) else None
            # Iconic games: the franchise's remembered nights, with the
            # per-team starred flags. Absent in old saves -> empty.
            team.iconic_games = [dict(e) for e in
                                 (team_data.get('iconic_games', None) or [])
                                 if isinstance(e, dict)][:30]
            # Team dynamics feed + dressing-room story state. Absent in
            # old saves -> empty, same as a fresh club.
            team.dynamics_log = [dict(e) for e in
                                 (team_data.get('dynamics_log', None) or [])][-100:]
            _dr = team_data.get('dressing_room', None)
            team.dressing_room = {
                k: (list(v) if isinstance(v, list)
                    else (dict(v) if isinstance(v, dict) else v))
                for k, v in _dr.items()
            } if isinstance(_dr, dict) else {}
            # Pro-scout storyline state (steal/sell watches, filed tips).
            _sw = team_data.get('scout_watches', None) or {}
            for _w in ('steal_watch', 'sell_watch', 'scout_buy_tips',
                       'scout_sell_tips', 'tip_ledger'):
                try:
                    setattr(team, _w, {
                        k: dict(v) for k, v in
                        ((_sw.get(_w, None)) or {}).items()})
                except Exception:
                    setattr(team, _w, {})
            # Standing line-control decision. Absent = old save -> coach.
            team.line_control = team_data.get('line_control', None) or 'coach'
            # Tactics choices + earned familiarity + saved preferences.
            _tx = team_data.get('tactics', None) or {}
            team.tactic_even_strength = _tx.get('even_strength', 'Balanced')
            team.tactic_power_play = _tx.get('power_play', 'Offensive')
            team.tactic_penalty_kill = _tx.get('penalty_kill', 'Defensive')
            team.tactic_line_matching = _tx.get('line_matching', 'Standard')
            team.tactic_forecheck = _tx.get('forecheck', '2-1-2')
            team.tactic_offense = _tx.get('offense', 'Spread')
            try:
                team.tactics_familiarity = float(_tx.get('familiarity', 85) or 85)
            except Exception:
                team.tactics_familiarity = 85.0
            team.tactics_installed_by = _tx.get('installed_by', None)
            team.preferred_tactics = dict(_tx.get('preferred', None) or {})
            # Parity-engine form/streak state.
            team._parity_state = dict(team_data.get('_parity_state', None) or {})
            # Analytics-GM identity.
            _ai = team_data.get('analytics_identity', None) or {}
            try:
                team.analytics_quality = int(_ai.get('quality', 35) or 0)
            except Exception:
                team.analytics_quality = 35
            try:
                team.analytics_philosophy = float(_ai.get('philosophy', 30.0) or 0.0)
            except Exception:
                team.analytics_philosophy = 30.0
            try:
                team.philosophy_baseline = float(_ai.get('baseline', 30.0) or 0.0)
            except Exception:
                team.philosophy_baseline = 30.0
            team._prev_gm_name = _ai.get('prev_gm_name', '') or ''
            # Analytics-hub snapshots (writer caps at 10).
            team.analytics_games = [dict(r) for r in
                                    (team_data.get('analytics_games', None) or [])][-10:]
            # GM name + profile. Absent in old saves -> defaults.
            team.gm_name = team_data.get('gm_name', None) or 'General Manager'
            _gp = team_data.get('gm_profile', None)
            if isinstance(_gp, dict) and _gp:
                try:
                    from game_classes import GMProfile
                    import dataclasses
                    _gfields = {f.name for f in dataclasses.fields(GMProfile)}
                    team.gm_profile = GMProfile(**{
                        k: v for k, v in _gp.items() if k in _gfields})
                except Exception:
                    pass
            
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

            # Restore inbox. Absent in old saves -> fresh empty inbox.
            try:
                from game_classes import EmailMessage, EmailInbox
                inbox = EmailInbox()
                for md in team_data.get('inbox', []) or []:
                    msg = EmailMessage.from_dict(md) if isinstance(md, dict) else None
                    if msg is not None:
                        inbox.messages.append(msg)
                inbox.unread_count = sum(1 for m in inbox.messages if not m.is_read)
                inbox.total_messages = len(inbox.messages)
                team.inbox = inbox
            except Exception:
                pass

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
                elif key == 'playoff_stats' and value:
                    player.playoff_stats = self._restore_player_stats(value)
                elif key == 'ahl_stats' and value:
                    player.ahl_stats = self._restore_player_stats(value)
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
                        # Stamp the flag: weekly ticks branch on it, and old
                        # saves predate the flag entirely. Clear every team
                        # first so a stale flag can never leave two user
                        # clubs behind.
                        try:
                            for t in self.game_manager.league.teams:
                                t.is_user_team = False
                            team.is_user_team = True
                        except Exception:
                            pass
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
                        _restored = {
                            'date': game_date,
                            'home_team': home_team,
                            'away_team': away_team,
                            'time': dt_time(19, 0),
                            'league': game_data.get('league', ''),
                        }
                        if game_data.get('outdoor'):
                            _restored['outdoor'] = game_data['outdoor']
                        schedule.append(_restored)
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

            gm = self.game_manager
            if hasattr(gm, 'database_manager') and gm.database_manager is not None:
                gm.database_manager.free_agents = free_agents
            else:
                gm.league.free_agents = free_agents

        except Exception as e:
            print(f"Error restoring free agents: {e}")

    # Fields that live on the native 1-100 scale (post-rescale this is every
    # attribute: players, morale, injury proneness, and all staff fields).
    _SCALE_100_PLAYER_FIELDS = (
        'acceleration', 'adaptability', 'aggressiveness', 'agility',
        'anticipation', 'backhand', 'balance', 'bodycheck', 'breakaway_skill',
        'breakout_passes', 'checking', 'coachability', 'composure',
        'confidence', 'consistency', 'creativity', 'decision_making',
        'defensive_awareness', 'deflections', 'deking', 'determination',
        'discipline', 'durability', 'endurance', 'faceoff_wins', 'faceoffs',
        'first_pass', 'flair', 'focus', 'forechecking', 'glove_hand',
        'goaltending', 'hockey_iq', 'important_matches', 'leadership',
        'loose_puck', 'off_the_puck', 'offensive_awareness', 'one_timer',
        'passing', 'passing_accuracy', 'passing_creativity', 'pokecheck',
        'positioning', 'pressure_player', 'puck_handling', 'puck_protection',
        'rebound_control', 'reflexes', 'screen_shots', 'shooting',
        'shooting_accuracy', 'shooting_power', 'shot_blocking', 'skating',
        'slapshot', 'speed', 'stamina', 'stick_side', 'stickhandling',
        'strength', 'teamwork', 'vision', 'work_ethic', 'wristshot',
    )

    def _migrate_legacy_attribute_scale(self, stamped_scale=None):
        """Double legacy ~50-scale attributes to the native 1-100 scale.

        Saves written before the scale audit store attributes around 25-50.
        Detection uses the league-wide mean of core attributes (legacy ~= 35,
        current ~= 72), so a single weak prospect can never trigger it.
        Runs once per load; already-migrated saves are detected as current.

        Saves stamped with attribute_scale >= 100 are NEVER migrated: the
        mean heuristic misfires on modern databases (large prospect pools
        drag the sampled mean under the 58 threshold), silently inflating
        attributes toward 100 on every first load.
        """
        if stamped_scale is not None and stamped_scale >= 100:
            return  # modern save; nothing to do
        gm = self.game_manager
        league = getattr(gm, 'league', None)
        if not league or not getattr(league, 'teams', None):
            return
        players = []
        for team in league.teams:
            for pool in ('roster', 'ahl_roster', 'prospects'):
                players.extend(getattr(team, pool, None) or [])
        dbm = getattr(gm, 'database_manager', None)
        if dbm is not None:
            players.extend(getattr(dbm, 'free_agents', None) or [])
        else:
            players.extend(getattr(league, 'free_agents', None) or [])
        for dc in (getattr(gm, 'draft_classes', None) or {}).values():
            players.extend(dc if isinstance(dc, list) else [])
        players = [p for p in players if p is not None]
        if len(players) < 20:
            return
        sample = []
        for p in players[:400]:
            for f in ('skating', 'shooting', 'passing'):
                v = getattr(p, f, None)
                if isinstance(v, (int, float)):
                    sample.append(v)
        if not sample:
            return
        mean = sum(sample) / len(sample)
        if mean >= 58:
            return  # current 1-100 scale; nothing to do
        migrated = 0
        for p in players:
            for f in self._SCALE_100_PLAYER_FIELDS:
                v = getattr(p, f, None)
                if isinstance(v, (int, float)) and v < 62:
                    setattr(p, f, min(100, int(round(v * 2))))
                    migrated += 1
            # Morale was 1-10, injury proneness 1-20 on legacy saves.
            v = getattr(p, 'morale', None)
            if isinstance(v, (int, float)) and v <= 10:
                setattr(p, 'morale', min(100, int(round(v * 10))))
                migrated += 1
            v = getattr(p, 'injury_proneness', None)
            if isinstance(v, (int, float)) and v <= 20:
                setattr(p, 'injury_proneness', min(100, int(round(v * 5))))
                migrated += 1
        # Staff: all 22 coaching attributes were 1-20, morale 5-17,
        # reputation 5-15. Post-rescale everything is 1-100.
        staff_fields = (
            'coaching_forwards', 'coaching_defensemen', 'coaching_goalies',
            'tactical_knowledge', 'game_preparation', 'match_preparation',
            'working_with_youngsters', 'player_development', 'man_management',
            'motivating', 'discipline', 'leadership',
            'judging_player_ability', 'judging_player_potential',
            'media_handling', 'determination', 'adaptability',
            'level_of_discipline', 'attacking_coaching', 'defensive_coaching',
            'mental_coaching', 'technical_coaching',
        )
        for team in league.teams:
            for s in getattr(team, 'staff', None) or []:
                for f in staff_fields:
                    v = getattr(s, f, None)
                    if isinstance(v, (int, float)) and v <= 20:
                        setattr(s, f, min(100, int(round(v * 5))))
                        migrated += 1
                v = getattr(s, 'morale', None)
                if isinstance(v, (int, float)) and v <= 20:
                    setattr(s, 'morale', min(100, int(round(v * 5))))
                    migrated += 1
                v = getattr(s, 'reputation', None)
                if isinstance(v, (int, float)) and v <= 20:
                    setattr(s, 'reputation', min(100, int(round(v * 5))))
                    migrated += 1
        print(f"Migrated {len(players)} players from legacy attribute scale "
              f"({migrated} fields doubled, mean was {mean:.1f})")
    
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




class SaveLoadView(ctk.CTkFrame):
    """UI view for saving and loading games (full-screen).

    Blocking callers (e.g. the exit-to-desktop flow) should pass
    ``on_done`` -- it is called with a result dict
    ``{'saved': bool, 'cancelled': bool, 'loaded': bool,
    'loaded_path': str|None}`` before the view closes.
    """

    def __init__(self, parent, app=None, mode='save', on_done=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the SaveLoadWindow wrapper
        self.configure(fg_color=BG)
        self.mode = mode  # 'save' or 'load'
        self.on_done = on_done
        self.save_manager = GameSaveManager(self.app)
        self.save_completed = False  # Flag for exit handling
        self.loaded_file_path = None  # For load mode integration
        self.was_cancelled = False  # Track if dialog was cancelled

        self._create_interface()
        self._refresh_file_list()


    def _show_banner(self, text, kind="info"):
        """Show an in-view message banner (replaces messagebox popups)."""
        colors = {"info": ("#1a3a5c", "#4a9eff"), "error": ("#5c1a1a", "#ff6b6b"),
                  "warn": ("#5c4a1a", "#ffcc00"), "ok": ("#1a5c2a", "#51cf66")}
        bg, fg = colors.get(kind, colors["info"])
        banner = getattr(self, "_banner", None)
        if banner is None:
            try:
                import customtkinter as ctk
                banner = ctk.CTkLabel(self, text="", fg_color=bg, text_color=fg,
                                      corner_radius=6)
                banner.pack(fill="x", padx=12, pady=(8, 0))
                try:
                    banner.lower()
                except Exception:
                    pass
                self._banner = banner
            except Exception:
                return
        banner.configure(text=text, fg_color=bg, text_color=fg)
        # auto-clear after 6s
        try:
            after = getattr(self, "_banner_after", None)
            if after:
                self.after_cancel(after)
            self._banner_after = self.after(6000, lambda: banner.configure(text=""))
        except Exception:
            pass

    def _ask_confirm(self, text, on_yes, on_no=None):
        """Show an in-view Yes/No panel (replaces messagebox.askyesno)."""
        old = getattr(self, "_confirm_panel", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass
        import customtkinter as ctk
        panel = ctk.CTkFrame(self, fg_color="#2a2a3a", corner_radius=8)
        panel.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(panel, text=text, wraplength=520).pack(padx=12, pady=(10, 6))
        btns = ctk.CTkFrame(panel, fg_color="transparent")
        btns.pack(pady=(0, 10))

        def _yes():
            try:
                panel.destroy()
            except Exception:
                pass
            self._confirm_panel = None
            on_yes()

        def _no():
            try:
                panel.destroy()
            except Exception:
                pass
            self._confirm_panel = None
            if on_no:
                on_no()

        ctk.CTkButton(btns, text="Yes", command=_yes, width=90).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="No", command=_no, width=90).pack(side="left", padx=6)
        self._confirm_panel = panel

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _notify_done(self, result):
        """Fire the on_done callback (blocking-flow replacement)."""
        cb = getattr(self, 'on_done', None)
        if callable(cb):
            try:
                cb(result)
            except Exception:
                pass

    def _result(self):
        return {'saved': self.save_completed,
                'cancelled': self.was_cancelled,
                'loaded': self.loaded_file_path is not None,
                'loaded_path': self.loaded_file_path}

    def on_window_close(self):
        """Handle window close events (X button, Alt+F4, Cancel buttons)."""
        # Set appropriate flags based on whether save was completed
        if not self.save_completed:
            self.was_cancelled = True

        self._notify_done(self._result())
        self.close_view()

    def _create_interface(self):
        """Create the save/load interface"""
        main_frame = ttk.Frame(self, style='Content.TFrame')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Title
        title_text = f"{'Save Game' if self.mode == 'save' else 'Load Game'}"
        title_label = ttk.Label(main_frame, text=title_text, style='Title.TLabel',
                               font=(self.app.FONT_FAMILY, 20, 'bold'))
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
                                 style='Card.TLabel', justify='left')
        preview_label.pack(padx=10, pady=10, anchor='w')

        # Quick save slots
        slots_frame = ttk.LabelFrame(parent, text="Quick Save Slots", style='Card.TLabelframe')
        slots_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self._create_quick_save_slots(slots_frame)

        # Quick save buttons
        quick_buttons_frame = ttk.Frame(parent, style='Content.TFrame')
        quick_buttons_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(quick_buttons_frame, text="Cancel",
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
                                       font=(self.app.FONT_FAMILY, 9))
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

        save_btn = ttk.Button(buttons_frame, text="Save Game",
                             command=self._advanced_save_game,
                             style='Accent.TButton')
        save_btn.pack(side='left', padx=(0, 10))

        save_as_btn = ttk.Button(buttons_frame, text="Save As...",
                                command=self._save_as_dialog,
                                style='TButton')
        save_as_btn.pack(side='left', padx=(0, 10))

        cancel_btn = ttk.Button(buttons_frame, text="Cancel",
                               command=self.on_window_close,
                               style='TButton')
        cancel_btn.pack(side='right')

    def _create_manage_saves_tab(self, parent):
        """Create save file management interface"""
        # File operations toolbar
        toolbar_frame = ttk.Frame(parent, style='Content.TFrame')
        toolbar_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(toolbar_frame, text="Open Save Folder",
                  command=self._open_save_folder, style='TButton').pack(side='left', padx=(0, 5))

        ttk.Button(toolbar_frame, text="Export Save",
                  command=self._export_save, style='TButton').pack(side='left', padx=5)

        ttk.Button(toolbar_frame, text="Import Save",
                  command=self._import_save, style='TButton').pack(side='left', padx=5)

        ttk.Button(toolbar_frame, text="Delete Selected",
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

                ttk.Button(slot_frame, text="Overwrite",
                          command=lambda s=i+1: self._quick_save_to_slot(s),
                          style='TButton').pack(side='right', padx=(0, 5))

                ttk.Button(slot_frame, text="Load",
                          command=lambda s=i+1: self._quick_load_from_slot(s),
                          style='TButton').pack(side='right', padx=5)
            else:
                # Empty slot
                empty_label = ttk.Label(slot_frame, text="<Empty Slot>",
                                       style='Content.TLabel', foreground='gray')
                empty_label.pack(side='left', padx=(5, 0))

                ttk.Button(slot_frame, text="Save Here",
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

        self.load_btn = ttk.Button(load_buttons_frame, text="Load Selected Game",
                                  command=self._load_game, style='Accent.TButton',
                                  state='disabled')
        self.load_btn.pack(side='left')

        cancel_btn = ttk.Button(load_buttons_frame, text="Cancel",
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
            self._show_banner("Please enter a save name", "error")
            return

        # Add .hm extension if not present
        if not save_name.endswith('.hm'):
            save_name += '.hm'

        # Check if file already exists
        filepath = os.path.join(self.save_manager.save_directory, save_name)
        if os.path.exists(filepath):
            self._ask_confirm(f"Save file '{save_name}' already exists. Overwrite?",
                              lambda: self._do_save_game(save_name))
            return
        self._do_save_game(save_name)

    def _do_save_game(self, save_name):
        """Perform the actual save (after overwrite confirmation)."""
        # Perform save
        success = self.save_manager.save_game(save_name, self.compress_var.get())

        if success:
            self._show_banner(f"Game saved successfully as '{save_name}'", "ok")
            self._refresh_file_list()
            self.save_completed = True  # Flag for exit handling
            self.app.on_game_saved()
            # Close the view after successful save
            self._notify_done(self._result())
            self.close_view()
        else:
            self._show_banner("Failed to save game", "error")

    def _advanced_save_game(self):
        """Save game with advanced options"""
        save_name = self.save_name_var.get().strip()
        if not save_name:
            self._show_banner("Please enter a save name", "error")
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

            result = None
            self._ask_confirm(f"Save file '{save_name}' already exists. Overwrite?",
                              lambda: self._do_advanced_save(save_name, filepath, category))
            return

        self._do_advanced_save(save_name, filepath, category)

    def _do_advanced_save(self, save_name, filepath, category):
        """Perform the advanced save (after overwrite confirmation)."""
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
            self._show_banner(f"Game saved successfully as '{save_name}'", "ok")
            self._refresh_file_list()
            self.save_completed = True  # Flag for exit handling
            self.app.on_game_saved()
            # Close the view after successful save
            self._notify_done(self._result())
            self.close_view()
        else:
            self._show_banner("Failed to save game", "error")

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
            self._show_banner(f"Game saved to Quick Save Slot {slot_number}", "ok")
            self._refresh_quick_save_slots()
            self.save_completed = True  # Flag for exit handling
            self.app.on_game_saved()
            # Close the view after successful quick save
            self._notify_done(self._result())
            self.close_view()
        else:
            self._show_banner(f"Failed to save to slot {slot_number}", "error")

    def _quick_load_from_slot(self, slot_number):
        """Load from a quick save slot"""
        slot_name = f"QuickSave_Slot_{slot_number}.hm"
        filepath = os.path.join(self.save_manager.save_directory, "QuickSaves", slot_name)

        if os.path.exists(filepath):
            self.save_manager.load_game(filepath)
        else:
            self._show_banner(f"Quick Save Slot {slot_number} is empty", "error")

    def _get_game_preview(self):
        """Get current game state preview"""
        try:
            preview_lines = []

            if hasattr(self.app, 'user_team') and self.app.user_team:
                preview_lines.append(f"Team: {self.app.user_team.team_name}")

                # Add roster info
                roster_count = len(getattr(self.app.user_team, 'roster', []))
                preview_lines.append(f"Roster Size: {roster_count} players")

            if hasattr(self.app, 'current_date'):
                preview_lines.append(f"Current Date: {self.app.current_date}")

            if hasattr(self.app, 'league') and self.app.league:
                preview_lines.append(f"Season: {getattr(self.app.league, 'season_year', 'Unknown')}")

            # Add record if available
            if hasattr(self.app, 'user_team') and self.app.user_team:
                wins = getattr(self.app.user_team, 'wins', 0)
                losses = getattr(self.app.user_team, 'losses', 0)
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
            if hasattr(self.app, 'user_team') and self.app.user_team:
                team_name = self.app.user_team.team_name.replace(" ", "_")

            # Date info
            now = datetime.now()
            date_str = now.strftime("%Y%m%d")
            time_str = now.strftime("%H%M")

            # Game date if available
            game_date_str = ""
            if hasattr(self.app, 'current_date'):
                game_date_str = self.app.current_date.strftime("%m_%d")

            # Season info
            season_str = ""
            if hasattr(self.app, 'league') and self.app.league:
                season_str = f"_{getattr(self.app.league, 'season_year', '')}"

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
        suggestion_window = InGamePopup(self)
        suggestion_window.title("Save Name Suggestions")
        suggestion_window.geometry("400x300")
        suggestion_window.configure(background=self.app.BG_COLOR)

        ttk.Label(suggestion_window, text="Choose a save name:",
                 style='Content.TLabel').pack(pady=10)

        # Suggestions listbox
        listbox_frame = ttk.Frame(suggestion_window, style='Content.TFrame')
        listbox_frame.pack(fill='both', expand=True, padx=20, pady=10)

        suggestions_listbox = tk.Listbox(listbox_frame, height=10,
                                        font=(self.app.FONT_FAMILY, 10))
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
                self._show_banner(f"Could not open save folder: {e}", "error")
        else:
            self._show_banner("Save folder does not exist", "error")

    def _export_save(self):
        """Export selected save file"""
        selection = self.file_tree.selection()
        if not selection:
            self._show_banner("Please select a save file to export", "warn")
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
                self._show_banner(f"Save file exported to:\n{export_path}", "ok")
            except Exception as e:
                self._show_banner(f"Failed to export save file:\n{str(e)}", "error")

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
                    self._ask_confirm(f"A save file named '{filename}' already exists. Overwrite?",
                                      lambda: self._do_import_file(import_path, dest_path))
                    return

                self._do_import_file(import_path, dest_path)

            except Exception as e:
                self._show_banner(f"Failed to import save file:\n{str(e)}", "error")

    def _do_import_file(self, import_path, dest_path):
        """Copy the import file (after overwrite confirmation)."""
        import shutil
        shutil.copy2(import_path, dest_path)
        self._show_banner("Save file imported successfully", "ok")
        self._refresh_file_list()

    def _delete_selected_save(self):
        """Delete selected save file"""
        selection = self.file_tree.selection()
        if not selection:
            self._show_banner("Please select a save file to delete", "warn")
            return

        # Get selected file info
        item = selection[0]
        filename = self.file_tree.set(item, 'filename')
        filepath = self.file_tree.set(item, 'filepath')

        # Confirm deletion
        self._ask_confirm(f"Are you sure you want to delete '{filename}'?\n\nThis action cannot be undone.",
                          lambda: self._do_delete_save(filepath, filename))

    def _do_delete_save(self, filepath, filename):
        """Delete the save file (after confirmation)."""
        try:
            os.remove(filepath)
            self._show_banner(f"Save file '{filename}' has been deleted", "ok")
            self._refresh_file_list()
        except Exception as e:
            self._show_banner(f"Failed to delete save file:\n{str(e)}", "error")

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
        new_name = simpledialog.askstring("Rename File",
                                           f"Enter new name for '{current_name}':",
                                           initialvalue=current_name.replace('.hm', ''))

        if new_name and new_name.strip():
            if not new_name.endswith('.hm'):
                new_name += '.hm'

            new_path = os.path.join(os.path.dirname(current_path), new_name)

            try:
                os.rename(current_path, new_path)
                self._show_banner(f"File renamed to '{new_name}'", "ok")
                self._refresh_file_list()
            except Exception as e:
                self._show_banner(f"Failed to rename file:\n{str(e)}", "error")

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
                self._show_banner("Could not read save file properties", "error")
        except Exception as e:
            self._show_banner(f"Failed to read file properties:\n{str(e)}", "error")

    def _show_save_properties_dialog(self, save_data, filepath):
        """Show save file properties in a dialog"""
        # Create properties window
        props_window = InGamePopup(self)
        props_window.title("Save File Properties")
        props_window.geometry("500x400")
        props_window.configure(background=self.app.BG_COLOR)

        # Create scrollable text widget to show properties
        text_frame = ttk.Frame(props_window, style='Content.TFrame')
        text_frame.pack(fill='both', expand=True, padx=20, pady=20)

        text_widget = tk.Text(text_frame, wrap='word',
                             font=(self.app.FONT_FAMILY, 10))
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
            self._show_banner("Please select a save file to load", "error")
            return

        # Get selected file path
        item = selection[0]
        filepath = self.file_tree.set(item, 'filepath')
        filename = self.file_tree.item(item)['values'][0]

        # Confirm load
        self._ask_confirm(f"Load game from '{filename}'?\n\nThis will replace your current game progress.",
                          lambda: self._do_load_game(filepath))
        return

    def _do_load_game(self, filepath):
        """Perform the load (after confirmation)."""
        # Perform load
        success = self.save_manager.load_game(filepath)

        if success:
            # Store loaded file path for main menu integration
            self.loaded_file_path = filepath
            # Notify parent if it has the callback
            if hasattr(self.app, 'on_game_loaded'):
                self.app.on_game_loaded()
            # Close the view after successful load
            self._notify_done(self._result())
            self.close_view()
        else:
            self._show_banner("Failed to load game", "error")


class SaveLoadWindow(InGamePopup):
    """Popup wrapper around SaveLoadView (backward compatibility).

    Keeps the old modal semantics so existing wait_window() call sites
    keep working until they are converted to the on_done pattern.
    """

    def __init__(self, parent, mode='save'):
        super().__init__(parent, modal=True)
        self.title(f"{'Save' if mode == 'save' else 'Load'} Game")
        app = (getattr(parent, 'app', None)
               or getattr(parent, 'parent', None) or parent)
        self._view = SaveLoadView(self, app=app, mode=mode)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)
        try:
            self.protocol("WM_DELETE_WINDOW", self._view.on_window_close)
        except Exception:
            pass

    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return InGamePopup.__getattr__(self, name)



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
