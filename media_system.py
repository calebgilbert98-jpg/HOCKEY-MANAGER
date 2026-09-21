# media_system.py
# Comprehensive Media & Press Conference System for Hockey Manager
# Fully optional system that adds immersive media interactions

import random
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum

class MediaEngagementLevel(Enum):
    """Player's chosen level of media engagement"""
    DISABLED = "Disabled"           # No media interactions
    MINIMAL = "Minimal"             # Only major events (trades, signings)  
    STANDARD = "Standard"           # Pre/post game + major events
    FULL = "Full Immersion"         # All interactions + storylines

class JournalistType(Enum):
    """Different types of journalists with different personalities"""
    SUPPORTIVE = "Supportive"       # Generally positive coverage
    NEUTRAL = "Neutral"             # Balanced reporting
    CRITICAL = "Critical"           # Tends to ask tough questions
    SENSATIONALIST = "Sensationalist" # Looks for drama/controversy

class StorylineType(Enum):
    """Types of ongoing storylines"""
    PLAYER_DEVELOPMENT = "Rising Star"
    VETERAN_LEADERSHIP = "Veteran Presence" 
    TRADE_RUMORS = "Trade Speculation"
    CONTRACT_DRAMA = "Contract Situation"
    RIVALRY = "Team Rivalry"
    PLAYOFF_PUSH = "Playoff Chase"
    REBUILD = "Organizational Rebuild"
    CHEMISTRY = "Locker Room Dynamics"

@dataclass
class Journalist:
    """Represents a media personality"""
    name: str
    outlet: str                    # TSN, ESPN, local paper, etc.
    type: JournalistType
    relationship: int              # -10 to +10, affects question tone
    beat: str                      # "NHL", "Local", "National"
    specialty: str                 # "Trades", "Prospects", "Analytics", etc.
    
    def get_question_tone(self) -> str:
        """Get the tone this journalist uses based on type and relationship"""
        base_tone = {
            JournalistType.SUPPORTIVE: 0.3,
            JournalistType.NEUTRAL: 0.0,
            JournalistType.CRITICAL: -0.3,
            JournalistType.SENSATIONALIST: -0.5
        }
        
        # Adjust based on relationship
        final_tone = base_tone[self.type] + (self.relationship * 0.05)
        
        if final_tone > 0.2:
            return "friendly"
        elif final_tone > -0.1:
            return "neutral"
        elif final_tone > -0.4:
            return "probing"
        else:
            return "hostile"

@dataclass
class MediaStoryline:
    """Represents an ongoing media storyline"""
    id: str
    type: StorylineType
    title: str
    description: str
    players_involved: List[str]    # Player IDs
    intensity: int                 # 1-10, affects how often it comes up
    duration_days: int             # How long story stays active
    created_date: date
    last_mentioned: date
    resolution: Optional[str] = None
    
    def is_active(self, current_date: date) -> bool:
        """Check if storyline is still active"""
        if self.resolution:
            return False
        days_since_creation = (current_date - self.created_date).days
        return days_since_creation < self.duration_days
    
    def should_mention(self, current_date: date) -> bool:
        """Determine if storyline should be mentioned in current context"""
        if not self.is_active(current_date):
            return False
        
        days_since_mention = (current_date - self.last_mentioned).days
        mention_probability = min(0.8, self.intensity * 0.08)
        
        # Higher chance if it's been a while since mention
        if days_since_mention > 7:
            mention_probability *= 1.5
        elif days_since_mention < 2:
            mention_probability *= 0.3
            
        return random.random() < mention_probability

@dataclass  
class MediaEvent:
    """Represents a media event requiring GM response"""
    id: str
    type: str  # 'post_game_interview', 'trade_interview', 'signing_interview'
    date: 'date'
    deadline: 'date'
    details: dict
    importance: int = 5  # 1-10 scale
    auto_handled: bool = False
    completed: bool = False

class MediaSystem:
    """Main media system controller - completely optional"""
    
    def __init__(self, game_manager):
        self.game_manager = game_manager
        self.engagement_level = MediaEngagementLevel.DISABLED
        self.journalists = []
        self.storylines = []
        self.media_events = []
        self.pending_events = []       # MediaEvent objects
        self.team_reputation = {}      # Team name -> reputation score
        self.gm_reputation = 50        # 0-100, affects media treatment
        
        # Configuration options
        self.auto_handle_minor_events = True  # Auto-handle routine interviews
        self.notification_style = "popup"     # "popup", "log", "disabled"
        
        # Initialize default journalists and storylines
        self._initialize_default_journalists()
        
    def set_engagement_level(self, level):
        """Player chooses their media engagement level"""
        # Convert string to enum if needed
        if isinstance(level, str):
            level_map = {
                "Disabled": MediaEngagementLevel.DISABLED,
                "Minimal": MediaEngagementLevel.MINIMAL,
                "Standard": MediaEngagementLevel.STANDARD,
                "Full Immersion": MediaEngagementLevel.FULL
            }
            level = level_map.get(level, MediaEngagementLevel.DISABLED)
        
        self.engagement_level = level
        
        if level == MediaEngagementLevel.DISABLED:
            # Clear any pending events
            self.media_events.clear()
            self.storylines.clear()
            print("📺 Media system disabled - you can focus on pure hockey management")
        elif level == MediaEngagementLevel.MINIMAL:
            print("📺 Minimal media coverage enabled - major events only")
        elif level == MediaEngagementLevel.STANDARD:
            print("📺 Standard media coverage enabled - pre/post game interviews")
        else:
            print("📺 Full media immersion enabled - complete storyline experience")
    
    def _initialize_default_journalists(self):
        """Create a pool of journalists with different personalities"""
        self.journalists = [
            # National reporters
            Journalist("Sarah Mitchell", "TSN", JournalistType.NEUTRAL, 0, "National", "Trades"),
            Journalist("Mike Rodriguez", "ESPN", JournalistType.SUPPORTIVE, 2, "National", "Analytics"),
            Journalist("Jennifer Walsh", "Sportsnet", JournalistType.CRITICAL, -1, "National", "Prospects"),
            
            # Beat reporters (relationship varies by team)
            Journalist("David Chen", "Local Sports", JournalistType.NEUTRAL, 0, "Local", "Team Coverage"),
            Journalist("Amanda Foster", "City Paper", JournalistType.SUPPORTIVE, 1, "Local", "Human Interest"),
            
            # Social media/blog
            Journalist("Hockey Insider", "Twitter", JournalistType.SENSATIONALIST, -2, "Social", "Rumors"),
            Journalist("The Hockey Analyst", "Blog", JournalistType.CRITICAL, 0, "Analytics", "Performance")
        ]
    
    def process_game_result(self, game_result):
        """Process post-game media opportunities"""
        if self.engagement_level == MediaEngagementLevel.DISABLED:
            return
        
        # Only process if minimal+ engagement
        if self.engagement_level in [MediaEngagementLevel.MINIMAL, MediaEngagementLevel.STANDARD, MediaEngagementLevel.FULL]:
            self._generate_post_game_media_event(game_result)
    
    def process_trade(self, trade_details):
        """Process media reaction to trades"""
        if self.engagement_level == MediaEngagementLevel.DISABLED:
            return
            
        # All levels above disabled get trade media
        self._generate_trade_media_event(trade_details)
    
    def process_signing(self, player, contract_details):
        """Process media reaction to signings"""
        if self.engagement_level == MediaEngagementLevel.DISABLED:
            return
            
        # Generate signing media event
        self._generate_signing_media_event(player, contract_details)
    
    def _generate_post_game_media_event(self, game_result):
        """Create post-game interview opportunity"""
        if self.engagement_level not in [MediaEngagementLevel.STANDARD, MediaEngagementLevel.FULL]:
            return
        
        # Select journalist based on game importance
        journalist = self._select_journalist_for_game(game_result)
        
        # Generate questions based on game performance
        questions = self._generate_post_game_questions(game_result, journalist)
        
        event = {
            'type': 'post_game_interview',
            'journalist': journalist,
            'questions': questions,
            'game_result': game_result,
            'optional': True,  # Player can choose to skip
            'impact_level': 'low'  # Minor impact on team morale
        }
        
        self.media_events.append(event)
    
    def _generate_trade_media_event(self, trade_details):
        """Create trade-related media event"""
        # Select multiple journalists for big trades
        journalists = [j for j in self.journalists if j.specialty in ["Trades", "Team Coverage"]]
        selected_journalist = random.choice(journalists)
        
        questions = self._generate_trade_questions(trade_details, selected_journalist)
        
        event = {
            'type': 'trade_announcement',
            'journalist': selected_journalist,
            'questions': questions,
            'trade_details': trade_details,
            'optional': False,  # Major events require some response
            'impact_level': 'medium'
        }
        
        self.media_events.append(event)
        
        # Create storylines around the trade
        self._create_trade_storylines(trade_details)
    
    def _generate_signing_media_event(self, player, contract_details):
        """Create contract signing media event"""
        if contract_details.get('value', 0) < 2000000:  # Only big signings get media attention
            return
        
        journalist = random.choice([j for j in self.journalists if j.beat in ["Local", "National"]])
        questions = self._generate_signing_questions(player, contract_details, journalist)
        
        event = {
            'type': 'contract_signing',
            'journalist': journalist,
            'questions': questions,
            'player': player,
            'contract': contract_details,
            'optional': self.engagement_level != MediaEngagementLevel.FULL,
            'impact_level': 'low' if contract_details.get('value', 0) < 5000000 else 'medium'
        }
        
        self.media_events.append(event)
    
    def _select_journalist_for_game(self, game_result):
        """Select appropriate journalist based on game context"""
        # Big games get national coverage
        if game_result.get('overtime') or abs(game_result.get('score_diff', 0)) >= 4:
            nationals = [j for j in self.journalists if j.beat == "National"]
            if nationals:
                return random.choice(nationals)
        
        # Regular games get local coverage
        locals = [j for j in self.journalists if j.beat == "Local"]
        return random.choice(locals) if locals else random.choice(self.journalists)
    
    def _generate_post_game_questions(self, game_result, journalist):
        """Generate context-appropriate post-game questions"""
        questions = []
        tone = journalist.get_question_tone()
        
        # Win/loss specific questions
        if game_result.get('won', False):
            if tone == "friendly":
                questions.append("Great win tonight! What was the key to your team's success?")
            elif tone == "neutral":
                questions.append("Walk us through what worked well for your team tonight.")
            else:
                questions.append("The win was good, but there were still some concerning moments. Thoughts?")
        else:
            if tone == "friendly":
                questions.append("Tough loss, but what positives can you take from tonight?")
            elif tone == "neutral":
                questions.append("What do you think went wrong out there tonight?")
            else:
                questions.append("Another disappointing loss. How do you explain this to the fans?")
        
        # Performance-specific questions
        if game_result.get('goals_for', 0) == 0:
            questions.append("The offense struggled to generate scoring tonight. What adjustments are needed?")
        elif game_result.get('goals_against', 0) >= 5:
            questions.append("Five goals against is concerning. Is this a goaltending or defensive issue?")
        
        # Add storyline-related questions if any are active
        for storyline in self.storylines:
            if storyline.should_mention(self.game_manager.current_date):
                questions.extend(self._get_storyline_questions(storyline, journalist))
        
        return questions[:3]  # Limit to 3 questions max
    
    def _generate_trade_questions(self, trade_details, journalist):
        """Generate trade-related questions"""
        questions = []
        tone = journalist.get_question_tone()
        
        # Opening question about the trade
        if tone == "friendly":
            questions.append(f"Tell us about the decision to trade {trade_details.get('player_out', 'the player')}.")
        elif tone == "neutral":
            questions.append(f"Walk us through the trade that sent {trade_details.get('player_out', 'the player')} to {trade_details.get('team_to', 'the other team')}.")
        else:
            questions.append(f"This trade has fans questioning the team's direction. Justify this move.")
        
        # Value/return questions
        questions.append("Do you feel you got fair value in return?")
        
        # Team direction
        if tone == "hostile":
            questions.append("How do you respond to critics who say this team is going nowhere?")
        else:
            questions.append("How does this trade fit into the team's long-term plans?")
        
        return questions
    
    def _generate_signing_questions(self, player, contract_details, journalist):
        """Generate contract signing questions"""
        questions = []
        tone = journalist.get_question_tone()
        
        value = contract_details.get('value', 0)
        term = contract_details.get('term', 1)
        
        # Opening question
        if tone == "friendly":
            questions.append(f"Congratulations on re-signing {player.full_name}. What does he bring to this team?")
        else:
            questions.append(f"${value:,} over {term} years for {player.full_name}. Break down this contract for us.")
        
        # Value question
        if value > 8000000:
            questions.append("That's significant money. How do you justify this investment?")
        elif value < player.overall_rating * 100000:
            questions.append("Some might say this is a bargain contract. How did you make this work?")
        
        return questions
    
    def _create_trade_storylines(self, trade_details):
        """Create ongoing storylines around trades"""
        if self.engagement_level != MediaEngagementLevel.FULL:
            return
        
        # Create trade aftermath storyline
        storyline = MediaStoryline(
            id=f"trade_{random.randint(1000, 9999)}",
            type=StorylineType.TRADE_RUMORS,
            title=f"Trade Aftermath: {trade_details.get('player_out', 'Player')} Deal",
            description=f"How will the trade impact both teams?",
            players_involved=[trade_details.get('player_out', ''), trade_details.get('player_in', '')],
            intensity=6,
            duration_days=30,
            created_date=self.game_manager.current_date,
            last_mentioned=self.game_manager.current_date
        )
        
        self.storylines.append(storyline)
    
    def _get_storyline_questions(self, storyline, journalist):
        """Get questions related to active storylines"""
        questions = []
        tone = journalist.get_question_tone()
        
        if storyline.type == StorylineType.TRADE_RUMORS:
            if tone == "hostile":
                questions.append("There are persistent rumors about more trades coming. Care to comment?")
            else:
                questions.append("Can you address the speculation about potential roster moves?")
        elif storyline.type == StorylineType.PLAYOFF_PUSH:
            questions.append("With the playoff race heating up, how confident are you in this team's chances?")
        elif storyline.type == StorylineType.PLAYER_DEVELOPMENT:
            questions.append(f"How has {storyline.players_involved[0] if storyline.players_involved else 'the young player'} been developing?")
        
        return questions
    
    def get_pending_media_events(self):
        """Get all pending media events for player interaction"""
        # Return MediaEvent objects that haven't been completed
        return [event for event in self.pending_events if not event.completed]
    
    def handle_media_response(self, event, response_choice):
        """Process player's response to media event"""
        if self.engagement_level == MediaEngagementLevel.DISABLED:
            return
        
        # Mark event as completed
        event['status'] = 'completed'
        event['response'] = response_choice
        
        # Apply consequences based on response
        self._apply_media_consequences(event, response_choice)
    
    def _apply_media_consequences(self, event, response_choice):
        """Apply consequences of media interactions"""
        impact_level = event.get('impact_level', 'low')
        
        # Adjust GM reputation
        reputation_change = 0
        if response_choice in ['professional', 'thoughtful', 'diplomatic']:
            reputation_change = 1 if impact_level == 'low' else 2
        elif response_choice in ['dismissive', 'hostile', 'controversial']:
            reputation_change = -1 if impact_level == 'low' else -3
        
        self.gm_reputation = max(0, min(100, self.gm_reputation + reputation_change))
        
        # Update journalist relationship
        journalist = event.get('journalist')
        if journalist and response_choice in ['professional', 'thoughtful']:
            journalist.relationship = min(10, journalist.relationship + 1)
        elif journalist and response_choice in ['dismissive', 'hostile']:
            journalist.relationship = max(-10, journalist.relationship - 1)
        
        # Team morale effects (minimal unless it's a big story)
        if impact_level in ['medium', 'high']:
            morale_change = 0
            if response_choice in ['supportive', 'confident']:
                morale_change = 1
            elif response_choice in ['uncertain', 'critical']:
                morale_change = -1
            
            # Apply to team morale (if morale system exists)
            if hasattr(self.game_manager, 'user_team') and self.game_manager.user_team:
                for player in self.game_manager.user_team.roster:
                    if hasattr(player, 'morale'):
                        player.morale = max(1, min(20, player.morale + morale_change))
    
    def generate_daily_storylines(self):
        """Generate new storylines based on current team situation"""
        if self.engagement_level != MediaEngagementLevel.FULL:
            return
        
        # Clean up expired storylines
        self.storylines = [s for s in self.storylines if s.is_active(self.game_manager.current_date)]
        
        # Chance to generate new storylines
        if len(self.storylines) < 3 and random.random() < 0.1:
            self._generate_random_storyline()
    
    def _generate_random_storyline(self):
        """Generate a random storyline based on team context"""
        user_team = getattr(self.game_manager, 'user_team', None)
        if not user_team:
            return
        
        storyline_types = [
            StorylineType.PLAYER_DEVELOPMENT,
            StorylineType.VETERAN_LEADERSHIP,
            StorylineType.PLAYOFF_PUSH,
            StorylineType.CHEMISTRY
        ]
        
        selected_type = random.choice(storyline_types)
        
        # Create storyline based on type
        if selected_type == StorylineType.PLAYER_DEVELOPMENT:
            young_players = [p for p in user_team.roster if p.age <= 22]
            if young_players:
                player = random.choice(young_players)
                storyline = MediaStoryline(
                    id=f"dev_{random.randint(1000, 9999)}",
                    type=selected_type,
                    title=f"Rising Star: {player.full_name}",
                    description=f"How is young {player.full_name} adapting to the NHL?",
                    players_involved=[player.id],
                    intensity=random.randint(3, 6),
                    duration_days=random.randint(14, 45),
                    created_date=self.game_manager.current_date,
                    last_mentioned=self.game_manager.current_date
                )
                self.storylines.append(storyline)
    
    def skip_all_pending_events(self):
        """Auto-handle all pending events with neutral responses"""
        for event in self.get_pending_media_events():
            self.handle_media_response(event, 'professional')
    
    def get_system_status(self):
        """Get current status of media system"""
        return {
            'engagement_level': self.engagement_level.value,
            'pending_events': len(self.get_pending_media_events()),
            'active_storylines': len([s for s in self.storylines if s.is_active(self.game_manager.current_date)]),
            'gm_reputation': self.gm_reputation,
            'avg_journalist_relationship': sum(j.relationship for j in self.journalists) / len(self.journalists) if self.journalists else 0
        }
    
    def process_trade(self, user_team, other_team, traded_players, received_players):
        """Process a trade and generate media events"""
        if self.engagement_level == MediaEngagementLevel.DISABLED:
            return
        
        # Create trade event
        trade_details = {
            'type': 'trade',
            'user_team': user_team.team_name,
            'other_team': other_team.team_name,
            'traded_players': [p.full_name for p in traded_players],
            'received_players': [p.full_name for p in received_players],
            'date': self.game_manager.current_date
        }
        
        # Generate media event based on engagement level
        if self.engagement_level == MediaEngagementLevel.MINIMAL:
            # Just add to news, no interview required
            player_names = ", ".join([p.full_name for p in traded_players])
            self.game_manager.add_news(f"Media discusses trade of {player_names} to {other_team.team_name}")
        else:
            # Create interview opportunity
            event = MediaEvent(
                id=f"trade_{random.randint(1000, 9999)}",
                type='trade_interview',
                date=self.game_manager.current_date,
                deadline=self.game_manager.current_date + timedelta(days=2),
                details=trade_details,
                importance=self._calculate_trade_importance(traded_players, received_players),
                auto_handled=self.engagement_level == MediaEngagementLevel.STANDARD
            )
            self.pending_events.append(event)
    
    def process_signing(self, player, team, contract_type, salary, years):
        """Process a contract signing and generate media events"""
        if self.engagement_level == MediaEngagementLevel.DISABLED:
            return
        
        signing_details = {
            'type': 'signing',
            'player': player.full_name,
            'team': team.team_name,
            'contract_type': contract_type,
            'salary': salary,
            'years': years,
            'date': self.game_manager.current_date
        }
        
        # Only major signings get interviews in Standard mode
        importance = self._calculate_signing_importance(player, salary)
        
        if self.engagement_level == MediaEngagementLevel.MINIMAL or importance < 4:
            # Just add to news
            action = "extended" if contract_type == 'extension' else "signed"
            self.game_manager.add_news(f"Media reports on {player.full_name} being {action} by {team.team_name}")
        else:
            # Create interview opportunity
            event = MediaEvent(
                id=f"signing_{random.randint(1000, 9999)}",
                type='signing_interview',
                date=self.game_manager.current_date,
                deadline=self.game_manager.current_date + timedelta(days=1),
                details=signing_details,
                importance=importance,
                auto_handled=self.engagement_level == MediaEngagementLevel.STANDARD
            )
            self.pending_events.append(event)
    
    def _calculate_trade_importance(self, traded_players, received_players):
        """Calculate importance of a trade (1-10 scale)"""
        max_rating_out = max([p.overall_rating() for p in traded_players], default=5)
        max_rating_in = max([p.overall_rating() for p in received_players], default=5)
        
        # Base importance on highest rated player involved
        importance = max(max_rating_out, max_rating_in) // 2
        
        # Major trades get more attention
        if len(traded_players) + len(received_players) >= 4:
            importance += 2
        
        return min(importance, 10)
    
    def _calculate_signing_importance(self, player, salary):
        """Calculate importance of a signing (1-10 scale)"""
        # Base on player rating
        importance = player.overall_rating() // 2
        
        # High salary signings get more attention
        if salary >= 5_000_000:
            importance += 2
        elif salary >= 2_000_000:
            importance += 1
        
        return min(importance, 10)
    
    def get_interview_questions(self, event):
        """Generate interview questions for a media event"""
        if event.type == 'post_game_interview':
            return self._generate_post_game_questions(event.details, random.choice(self.journalists))
        elif event.type == 'trade_interview':
            return self._generate_trade_questions(event.details, random.choice(self.journalists))
        elif event.type == 'signing_interview':
            return self._generate_signing_questions(event.details, random.choice(self.journalists))
        return ["No questions available."]
    
    def _generate_signing_questions(self, signing_details, journalist):
        """Generate signing-related questions"""
        questions = []
        tone = journalist.get_question_tone()
        player = signing_details.get('player', 'the player')
        salary = signing_details.get('salary', 0)
        years = signing_details.get('years', 1)
        
        # Opening question
        if tone == "friendly":
            questions.append(f"Tell us about bringing {player} to the organization.")
        elif tone == "neutral":
            questions.append(f"What attracted you to {player} as a signing target?")
        else:
            questions.append(f"Is {player} worth ${salary:,} per year?")
        
        # Contract details
        questions.append(f"How do you justify the {years}-year contract length?")
        
        # Team fit
        if tone == "hostile":
            questions.append("This signing has raised questions about salary cap management. Your response?")
        else:
            questions.append(f"Where do you see {player} fitting into your lineup?")
        
        return questions[:3]