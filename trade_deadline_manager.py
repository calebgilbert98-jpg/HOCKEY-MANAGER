"""
Trade Deadline Manager - Core Backend Logic for Trade Deadline Day
Handles deadline detection, trade validation, and deadline-specific trading rules
"""

import random
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple, Any
import json


class TradeDeadlineManager:
    """Manages all trade deadline day logic and constraints"""
    
    # NHL Trade Deadline Constants
    DEADLINE_MONTH = 3
    DEADLINE_DAY = 8
    DEADLINE_HOUR = 15  # 3 PM ET
    DEADLINE_MINUTE = 0
    
    def __init__(self, game_manager=None):
        self.game_manager = game_manager
        self.deadline_passed = False
        self.emergency_trades_enabled = False
        self.trade_activity_log = []
        self.market_activity = {}
        self.team_strategies = {}
        self.deadline_stats = {
            'total_trades': 0,
            'players_moved': 0,
            'biggest_deal_value': 0,
            'most_active_team': None,
            'deadline_minute_trades': 0
        }
        
        # Breaking news tracking
        self.breaking_news = []
        self.last_breaking_news_check = datetime.now()
        
        # Initialize team market activity
        self._initialize_team_strategies()
        
    def is_trade_deadline_day(self, current_date=None) -> bool:
        """Check if the current date is trade deadline day"""
        check_date = current_date or datetime.now()
        return (check_date.month == self.DEADLINE_MONTH and 
                check_date.day == self.DEADLINE_DAY)
    
    def is_deadline_passed(self, current_datetime=None) -> bool:
        """Check if the trade deadline has passed (3 PM ET)"""
        if self.deadline_passed:
            return True
            
        check_time = current_datetime or datetime.now()
        if not self.is_trade_deadline_day(check_time):
            return False
            
        deadline_time = check_time.replace(
            hour=self.DEADLINE_HOUR, 
            minute=self.DEADLINE_MINUTE, 
            second=0, 
            microsecond=0
        )
        
        if check_time >= deadline_time:
            self.deadline_passed = True
            return True
            
        return False
    
    def get_time_until_deadline(self) -> Dict[str, Any]:
        """Get time remaining until trade deadline"""
        now = datetime.now()
        
        if not self.is_trade_deadline_day(now):
            # Find next trade deadline
            next_year = now.year if now.month <= self.DEADLINE_MONTH else now.year + 1
            next_deadline = datetime(next_year, self.DEADLINE_MONTH, self.DEADLINE_DAY, 
                                   self.DEADLINE_HOUR, self.DEADLINE_MINUTE)
        else:
            # Today is deadline day
            next_deadline = now.replace(hour=self.DEADLINE_HOUR, minute=self.DEADLINE_MINUTE, 
                                      second=0, microsecond=0)
        
        if now >= next_deadline:
            return {
                'expired': True,
                'time_left': timedelta(0),
                'formatted': "DEADLINE PASSED",
                'urgency': 'expired'
            }
        
        time_left = next_deadline - now
        total_seconds = int(time_left.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # Determine urgency level
        urgency = 'normal'
        if time_left <= timedelta(hours=1):
            urgency = 'critical'
        elif time_left <= timedelta(hours=6):
            urgency = 'high'
        elif time_left <= timedelta(days=1):
            urgency = 'medium'
        
        return {
            'expired': False,
            'time_left': time_left,
            'formatted': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            'hours': hours,
            'minutes': minutes,
            'seconds': seconds,
            'urgency': urgency,
            'deadline_datetime': next_deadline
        }
    
    def validate_trade_deadline_constraints(self, trade_proposal: Dict) -> Dict[str, Any]:
        """Validate if a trade can be completed under deadline constraints"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'deadline_specific': True
        }
        
        # Check if deadline has passed
        if self.is_deadline_passed():
            validation_result['valid'] = False
            validation_result['errors'].append("Trade deadline has passed (3 PM ET)")
            return validation_result
        
        # Check time remaining for complexity
        time_info = self.get_time_until_deadline()
        if not time_info['expired']:
            if time_info['urgency'] == 'critical':
                # Under 1 hour - only simple trades allowed
                involved_players = len(trade_proposal.get('players_offered', [])) + len(trade_proposal.get('players_wanted', []))
                if involved_players > 4:
                    validation_result['warnings'].append("Complex trades may not complete before deadline")
                
            elif time_info['urgency'] == 'high':
                # Under 6 hours - warn about complex trades
                involved_teams = len(set([trade_proposal.get('offering_team', ''), trade_proposal.get('receiving_team', '')]))
                if involved_teams > 2:
                    validation_result['warnings'].append("Multi-team trades discouraged close to deadline")
        
        # Check emergency trade flags
        if trade_proposal.get('emergency_trade', False):
            if not self.emergency_trades_enabled:
                validation_result['errors'].append("Emergency trades not currently enabled")
        
        # Salary cap verification near deadline
        if time_info['urgency'] in ['high', 'critical']:
            validation_result['warnings'].append("Verify salary cap implications before deadline")
        
        return validation_result
    
    def process_deadline_trade(self, trade_data: Dict) -> Dict[str, Any]:
        """Process a trade with deadline-specific handling"""
        result = {
            'success': False,
            'trade_id': None,
            'timestamp': datetime.now(),
            'errors': [],
            'warnings': []
        }
        
        # Validate trade under deadline constraints
        validation = self.validate_trade_deadline_constraints(trade_data)
        if not validation['valid']:
            result['errors'].extend(validation['errors'])
            return result
        
        # Add deadline-specific trade ID
        trade_id = self._generate_deadline_trade_id()
        result['trade_id'] = trade_id
        
        # Log trade activity
        self._log_trade_activity(trade_data, trade_id)
        
        # Update deadline statistics
        self._update_deadline_stats(trade_data)
        
        # Update team market activity
        self._update_team_activity(trade_data)
        
        result['success'] = True
        result['warnings'].extend(validation['warnings'])
        
        return result
    
    def get_market_temperature(self) -> Dict[str, str]:
        """Get current market temperature by position"""
        # Simulate market activity levels
        current_time = self.get_time_until_deadline()
        
        # Market gets hotter closer to deadline
        base_heat = 'cold'
        if not current_time['expired']:
            if current_time['urgency'] == 'critical':
                base_heat = 'blazing'
            elif current_time['urgency'] == 'high':
                base_heat = 'hot'
            elif current_time['urgency'] == 'medium':
                base_heat = 'warm'
        
        # Position-specific adjustments
        return {
            'forwards': base_heat,
            'defensemen': 'warm' if base_heat == 'cold' else base_heat,
            'goalies': 'cold' if base_heat in ['cold', 'warm'] else 'warm',
            'prospects': 'cold',
            'overall': base_heat
        }
    
    def generate_trade_activity(self) -> List[Dict]:
        """Generate simulated trade activity for deadline day"""
        if not self.is_trade_deadline_day():
            return []
        
        time_info = self.get_time_until_deadline()
        if time_info['expired']:
            return []
        
        # Generate more activity closer to deadline
        activity_multiplier = 1
        if time_info['urgency'] == 'critical':
            activity_multiplier = 4
        elif time_info['urgency'] == 'high':
            activity_multiplier = 3
        elif time_info['urgency'] == 'medium':
            activity_multiplier = 2
        
        trade_scenarios = [
            {
                'type': 'rental',
                'description': "{team1} acquires rental {position} from {team2}",
                'impact': 'medium',
                'positions': ['forward', 'defenseman']
            },
            {
                'type': 'futures',
                'description': "{team1} trades veteran {position} to {team2} for prospects",
                'impact': 'high',
                'positions': ['forward', 'defenseman', 'goalie']
            },
            {
                'type': 'depth',
                'description': "{team1} adds depth {position} from {team2}",
                'impact': 'low',
                'positions': ['forward', 'defenseman']
            },
            {
                'type': 'blockbuster',
                'description': "BLOCKBUSTER: {team1} and {team2} complete major deal",
                'impact': 'huge',
                'positions': ['multiple']
            }
        ]
        
        generated_activity = []
        
        # Generate random number of trades based on urgency
        num_trades = random.randint(1, 3) * activity_multiplier
        
        for _ in range(min(num_trades, 8)):  # Cap at 8 trades per generation
            scenario = random.choice(trade_scenarios)
            
            # Don't generate too many blockbusters
            if scenario['type'] == 'blockbuster' and random.random() > 0.1:
                scenario = random.choice([s for s in trade_scenarios if s['type'] != 'blockbuster'])
            
            # Generate random teams
            team1, team2 = self._get_random_trading_teams()
            position = random.choice(scenario['positions'])
            
            trade = {
                'timestamp': datetime.now(),
                'type': scenario['type'],
                'description': scenario['description'].format(
                    team1=team1, team2=team2, position=position
                ),
                'impact': scenario['impact'],
                'teams_involved': [team1, team2],
                'urgency_level': time_info['urgency']
            }
            
            generated_activity.append(trade)
            
        return generated_activity
    
    def get_team_activity_status(self) -> Dict[str, Dict]:
        """Get trading activity status for all teams"""
        teams = self._get_all_team_names()
        activity_status = {}
        
        for team in teams:
            # Get team's trading strategy and activity
            strategy = self.team_strategies.get(team, 'neutral')
            recent_activity = len([
                activity for activity in self.trade_activity_log[-10:]  # Last 10 trades
                if team in activity.get('teams_involved', [])
            ])
            
            # Determine activity level
            if recent_activity >= 3:
                activity_level = 'hot'
                indicator = '🔥'
            elif recent_activity >= 1:
                activity_level = 'warm'
                indicator = '🟡'
            else:
                activity_level = 'quiet'
                indicator = '⚪'
            
            activity_status[team] = {
                'activity_level': activity_level,
                'indicator': indicator,
                'strategy': strategy,
                'recent_trades': recent_activity,
                'status_text': strategy.upper() if strategy != 'neutral' else activity_level.upper()
            }
        
        return activity_status
    
    def _initialize_team_strategies(self):
        """Initialize team trading strategies for deadline day"""
        teams = self._get_all_team_names()
        
        strategies = ['buying', 'selling', 'neutral']
        
        for team in teams:
            # Assign random strategies with realistic distribution
            rand = random.random()
            if rand < 0.3:
                strategy = 'buying'  # 30% buyers
            elif rand < 0.5:
                strategy = 'selling'  # 20% sellers
            else:
                strategy = 'neutral'  # 50% neutral/quiet
            
            self.team_strategies[team] = strategy
    
    def _get_all_team_names(self) -> List[str]:
        """Get list of all NHL team names for simulation"""
        return [
            'BOS', 'NYR', 'TOR', 'TBL', 'FLA', 'BUF', 'DET', 'MTL', 'OTT', 'NYI', 'NJD', 'PHI',
            'CAR', 'WSH', 'PIT', 'CBJ', 'VGK', 'COL', 'DAL', 'MIN', 'WPG', 'NSH', 'STL', 'CHI',
            'EDM', 'VAN', 'CGY', 'SEA', 'LAK', 'ANA', 'SJS', 'ARI'
        ]
    
    def _get_random_trading_teams(self) -> Tuple[str, str]:
        """Get two random teams for simulated trades"""
        teams = self._get_all_team_names()
        team1 = random.choice(teams)
        team2 = random.choice([t for t in teams if t != team1])
        return team1, team2
    
    def _generate_deadline_trade_id(self) -> str:
        """Generate unique trade ID for deadline day"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = f"{random.randint(1000, 9999)}"
        return f"TDL_{timestamp}_{random_suffix}"
    
    def _log_trade_activity(self, trade_data: Dict, trade_id: str):
        """Log trade activity for deadline day tracking"""
        log_entry = {
            'trade_id': trade_id,
            'timestamp': datetime.now(),
            'teams_involved': [trade_data.get('offering_team', ''), trade_data.get('receiving_team', '')],
            'players_count': len(trade_data.get('players_offered', [])) + len(trade_data.get('players_wanted', [])),
            'trade_type': trade_data.get('trade_type', 'standard'),
            'time_until_deadline': self.get_time_until_deadline()['formatted']
        }
        
        self.trade_activity_log.append(log_entry)
        
        # Keep only last 50 trades to prevent memory issues
        if len(self.trade_activity_log) > 50:
            self.trade_activity_log = self.trade_activity_log[-50:]
    
    def _update_deadline_stats(self, trade_data: Dict):
        """Update deadline day statistics"""
        self.deadline_stats['total_trades'] += 1
        
        players_moved = len(trade_data.get('players_offered', [])) + len(trade_data.get('players_wanted', []))
        self.deadline_stats['players_moved'] += players_moved
        
        # Check if this was a last-minute trade (within 1 hour of deadline)
        time_info = self.get_time_until_deadline()
        if time_info['urgency'] == 'critical':
            self.deadline_stats['deadline_minute_trades'] += 1
    
    def _update_team_activity(self, trade_data: Dict):
        """Update team activity levels based on completed trade"""
        teams = [trade_data.get('offering_team', ''), trade_data.get('receiving_team', '')]
        
        for team in teams:
            if team and team in self.market_activity:
                self.market_activity[team]['recent_trades'] += 1
                
                # Update activity level based on recent trades
                recent_count = self.market_activity[team]['recent_trades']
                if recent_count >= 3:
                    self.market_activity[team]['level'] = 'hot'
                elif recent_count >= 1:
                    self.market_activity[team]['level'] = 'warm'
    
    def get_deadline_summary(self) -> Dict[str, Any]:
        """Get comprehensive deadline day summary"""
        return {
            'deadline_info': {
                'is_deadline_day': self.is_trade_deadline_day(),
                'deadline_passed': self.is_deadline_passed(),
                'time_remaining': self.get_time_until_deadline()
            },
            'market_info': {
                'temperature': self.get_market_temperature(),
                'team_activity': self.get_team_activity_status()
            },
            'statistics': self.deadline_stats,
            'recent_activity': self.trade_activity_log[-10:] if self.trade_activity_log else []
        }
    
    def get_breaking_news(self) -> List[str]:
        """Generate breaking news items for deadline day"""
        now = datetime.now()
        
        # Only generate breaking news on deadline day
        if not self.is_trade_deadline_day(now):
            return []
        
        # Check if enough time has passed since last news update
        if (now - self.last_breaking_news_check).total_seconds() < 120:  # 2 minutes minimum
            return []
            
        self.last_breaking_news_check = now
        
        time_info = self.get_time_until_deadline()
        
        # Generate breaking news based on urgency and time
        news_items = []
        
        if time_info['urgency'] == 'critical':
            # Last hour - lots of activity
            critical_news = [
                f"BREAKING: Multiple teams making last-minute moves before 3 PM deadline!",
                f"URGENT: {random.choice(['TOR', 'BOS', 'NYR', 'TBL', 'FLA'])} finalizing major deal in final minutes!",
                f"DEADLINE FRENZY: Trade calls flooding NHL offices with {time_info['formatted']} remaining!",
                f"LAST MINUTE: Several GMs working phones frantically to beat deadline!"
            ]
            news_items.extend(random.sample(critical_news, min(2, len(critical_news))))
            
        elif time_info['urgency'] == 'high':
            # Final hours - building tension
            high_urgency_news = [
                f"Market heating up: {random.choice(['COL', 'EDM', 'DAL', 'VGK'])} in serious talks for rental player",
                f"Sources: Big name player expected to move before deadline",
                f"Deadline approaching: Teams making final decisions on roster moves",
                f"Trade activity accelerating as deadline looms"
            ]
            news_items.extend(random.sample(high_urgency_news, 1))
            
        elif time_info['urgency'] == 'medium':
            # Morning activity
            medium_news = [
                f"Trade Deadline Day: Teams assessing final options", 
                f"GM calls increasing as deadline approaches",
                f"Several players on waivers ahead of deadline",
                f"Contenders finalizing trade deadline strategy"
            ]
            news_items.extend(random.sample(medium_news, 1))
        
        # Add random major trade announcements
        if random.random() < 0.3:  # 30% chance
            major_trades = [
                f"TRADE: Veteran defenseman moves to playoff contender",
                f"BLOCKBUSTER: Multi-player deal reshapes playoff race",
                f"RENTAL MARKET: Top scorer traded for future considerations", 
                f"SURPRISE MOVE: Unexpected player on the move before deadline"
            ]
            news_items.extend(random.sample(major_trades, 1))
            
        # Store in breaking news log
        self.breaking_news.extend(news_items)
        
        return news_items
    
    def get_market_intelligence(self) -> Dict[str, Any]:
        """Get comprehensive market intelligence and analysis"""
        return {
            'buyer_teams': self._identify_buyer_teams(),
            'seller_teams': self._identify_seller_teams(),
            'position_needs': self._analyze_position_needs(),
            'salary_cap_space': self._get_salary_cap_analysis(),
            'trade_predictions': self._generate_trade_predictions(),
            'deadline_trends': self._analyze_deadline_trends()
        }
    
    def _identify_buyer_teams(self) -> List[Dict[str, Any]]:
        """Identify teams likely to be buyers at the deadline"""
        buyer_teams = []
        
        # Mock analysis based on team strategies
        potential_buyers = ['TOR', 'BOS', 'NYR', 'TBL', 'FLA', 'COL', 'EDM', 'VGK', 'DAL', 'CAR']
        
        for team in potential_buyers:
            if self.team_strategies.get(team, 'neutral') == 'buyer':
                buyer_info = {
                    'team': team,
                    'likelihood': random.choice(['High', 'Medium', 'Low']),
                    'cap_space': f"${random.randint(2, 15)}M",
                    'primary_need': random.choice(['Forward', 'Defenseman', 'Goalie', 'Depth']),
                    'urgency': random.choice(['Critical', 'High', 'Medium']),
                    'assets': random.choice(['Rich in picks', 'Top prospects', 'Salary flexibility']),
                    'recent_activity': random.choice(['Very Active', 'Moderate', 'Quiet'])
                }
                buyer_teams.append(buyer_info)
        
        return buyer_teams
    
    def _identify_seller_teams(self) -> List[Dict[str, Any]]:
        """Identify teams likely to be sellers at the deadline"""
        seller_teams = []
        
        # Mock analysis
        potential_sellers = ['ARI', 'CHI', 'ANA', 'SJS', 'MTL', 'OTT', 'CBJ', 'BUF', 'DET', 'SEA']
        
        for team in potential_sellers:
            if self.team_strategies.get(team, 'neutral') == 'seller':
                seller_info = {
                    'team': team,
                    'likelihood': random.choice(['High', 'Medium', 'Low']),
                    'notable_assets': random.choice([
                        'Veteran forward (rental)',
                        'Top-4 defenseman',
                        'Backup goaltender',
                        'Expiring contracts'
                    ]),
                    'asking_price': random.choice(['High', 'Reasonable', 'Flexible']),
                    'timeline': random.choice(['Immediate', 'Before deadline', 'Best offer']),
                    'rebuild_focus': random.choice(['Picks', 'Prospects', 'Youth'])
                }
                seller_teams.append(seller_info)
        
        return seller_teams
    
    def _analyze_position_needs(self) -> Dict[str, List[str]]:
        """Analyze position needs across the league"""
        return {
            'forwards': ['TOR', 'NYR', 'COL', 'EDM', 'VGK', 'DAL'],
            'defensemen': ['BOS', 'TBL', 'FLA', 'CAR', 'WPG', 'MIN'],
            'goalies': ['TOR', 'EDM', 'COL', 'NJD', 'WSH'],
            'depth': ['NYR', 'BOS', 'FLA', 'VGK', 'SEA'],
            'rental_forwards': ['TBL', 'CAR', 'DAL', 'VGK', 'MIN'],
            'veteran_presence': ['COL', 'EDM', 'TOR', 'BOS', 'NYR']
        }
    
    def _get_salary_cap_analysis(self) -> Dict[str, Dict]:
        """Analyze salary cap situations across teams"""
        cap_analysis = {}
        
        # Mock salary cap data for key teams
        teams = ['TOR', 'BOS', 'NYR', 'TBL', 'FLA', 'COL', 'EDM', 'VGK', 'DAL', 'CAR']
        
        for team in teams:
            cap_analysis[team] = {
                'current_cap_hit': random.randint(78000000, 83500000),
                'cap_space': random.randint(500000, 15000000),
                'deadline_space': random.randint(2000000, 25000000),  # With LTIR/retention
                'flexibility': random.choice(['High', 'Medium', 'Low', 'None']),
                'retention_slots': random.randint(0, 3),
                'ltir_available': random.choice([True, False])
            }
        
        return cap_analysis
    
    def _generate_trade_predictions(self) -> List[Dict[str, Any]]:
        """Generate trade predictions based on market analysis"""
        predictions = []
        
        # High-likelihood trades
        high_likelihood = [
            {
                'likelihood': 85,
                'description': "Veteran forward rental to playoff contender",
                'teams_involved': ['TOR', 'ARI'],
                'assets': "2nd round pick + prospect",
                'reasoning': "TOR needs scoring depth, ARI has rental forwards"
            },
            {
                'likelihood': 78,
                'description': "Top-4 defenseman to Cup contender",
                'teams_involved': ['BOS', 'CHI'],
                'assets': "1st round pick + young player",
                'reasoning': "BOS needs defensive help, CHI rebuilding"
            }
        ]
        
        # Medium-likelihood trades
        medium_likelihood = [
            {
                'likelihood': 65,
                'description': "Goaltender depth move",
                'teams_involved': ['EDM', 'ANA'],
                'assets': "3rd round pick",
                'reasoning': "EDM goalie uncertainty, ANA has depth"
            },
            {
                'likelihood': 58,
                'description': "Salary dump with sweetener",
                'teams_involved': ['VGK', 'OTT'],
                'assets': "Player + 2nd round pick",
                'reasoning': "VGK cap issues, OTT has space"
            }
        ]
        
        # Surprise possibilities
        surprise_trades = [
            {
                'likelihood': 25,
                'description': "Blockbuster multi-player deal",
                'teams_involved': ['NYR', 'CAR'],
                'assets': "Multiple players and picks",
                'reasoning': "Both teams addressing major needs"
            }
        ]
        
        predictions.extend(high_likelihood)
        predictions.extend(medium_likelihood)
        predictions.extend(surprise_trades)
        
        return predictions
    
    def _analyze_deadline_trends(self) -> Dict[str, Any]:
        """Analyze current deadline trends and patterns"""
        return {
            'most_active_position': 'Forwards',
            'average_trade_size': 2.3,
            'rental_vs_futures': {
                'rental': 65,
                'futures': 35
            },
            'price_trends': {
                'rentals': 'Increasing',
                'defensemen': 'Premium pricing',
                'goalies': 'Stable',
                'picks': 'High demand'
            },
            'timing_patterns': {
                'early_movers': ['ARI', 'SJS', 'CHI'],
                'deadline_day_active': ['TOR', 'BOS', 'NYR'],
                'last_minute': ['TBL', 'VGK', 'COL']
            },
            'market_sentiment': 'Aggressive buying by contenders'
        }


def get_deadline_manager(game_manager=None) -> TradeDeadlineManager:
    """Get singleton instance of trade deadline manager"""
    if not hasattr(get_deadline_manager, '_instance'):
        get_deadline_manager._instance = TradeDeadlineManager(game_manager)
    return get_deadline_manager._instance