# automated_season_flow.py
# Automated Season Flow System for Hockey Manager
# Provides intelligent season progression and milestone detection

from datetime import date, timedelta
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable
import random

class SeasonPhase(Enum):
    """Different phases of the hockey season"""
    PRE_SEASON = "Pre-Season"
    REGULAR_SEASON = "Regular Season"  
    TRADE_DEADLINE = "Trade Deadline Period"
    PLAYOFF_PUSH = "Playoff Push"
    PLAYOFFS = "Playoffs"
    DRAFT_LOTTERY = "Draft Lottery"
    ENTRY_DRAFT = "Entry Draft"
    FREE_AGENCY = "Free Agency"
    OFF_SEASON = "Off-Season"

class AutoAdvanceMode(Enum):
    """Different auto-advance modes"""
    MANUAL = "Manual"           # User clicks continue for each day
    AUTO_NON_GAME = "Auto Non-Game Days"  # Auto-advance through days with no games
    AUTO_TO_NEXT_GAME = "Auto to Next Game"  # Auto-advance to next user team game
    AUTO_TO_MILESTONE = "Auto to Milestone"  # Auto-advance to next major milestone
    FULL_AUTO = "Full Automation"  # Fully automated season

@dataclass
class SeasonMilestone:
    """Represents an important date in the season"""
    date: date
    name: str
    phase: SeasonPhase
    description: str
    action: Optional[Callable] = None
    is_critical: bool = False  # Requires user attention

@dataclass 
class AutomationSettings:
    """Settings for automated season progression"""
    mode: AutoAdvanceMode = AutoAdvanceMode.MANUAL
    simulate_away_games: bool = True
    show_game_viewer_for_home: bool = True
    show_game_viewer_for_away: bool = False
    pause_at_milestones: bool = True
    pause_at_user_games: bool = True
    auto_skip_offseason: bool = False
    days_per_second: float = 1.0  # Speed of automation

class AutomatedSeasonFlow:
    """Manages automated season progression and milestone detection"""
    
    def __init__(self, game_manager):
        self.game_manager = game_manager
        self.settings = AutomationSettings()
        self.current_phase = SeasonPhase.REGULAR_SEASON
        self.milestones = []
        self.automation_active = False
        self.callbacks = {}
        
        # Initialize season milestones
        self._setup_season_milestones()
        
    def _setup_season_milestones(self):
        """Setup the key dates and milestones for the season"""
        if hasattr(self.game_manager, 'league') and hasattr(self.game_manager.league, 'season_year'):
            year = self.game_manager.league.season_year
        else:
            year = 2024  # Default year
            
        # Clear existing milestones
        self.milestones = []
        
        # Regular Season Milestones
        self.milestones.extend([
            SeasonMilestone(
                date=date(year, 11, 1),
                name="November Check-in",
                phase=SeasonPhase.REGULAR_SEASON,
                description="Early season assessment - team performance review",
                action=self._november_checkin
            ),
            SeasonMilestone(
                date=date(year, 12, 25),
                name="Christmas Break",
                phase=SeasonPhase.REGULAR_SEASON,
                description="Holiday break - roster freeze period",
                action=self._christmas_break
            ),
            SeasonMilestone(
                date=date(year + 1, 1, 1),
                name="New Year",
                phase=SeasonPhase.REGULAR_SEASON,
                description="New Year - second half of season begins",
                action=self._new_year_milestone
            ),
            SeasonMilestone(
                date=date(year + 1, 2, 1),
                name="February Push",
                phase=SeasonPhase.TRADE_DEADLINE,
                description="Trade deadline approaches - decision time",
                action=self._february_push
            ),
            SeasonMilestone(
                date=date(year + 1, 3, 8),
                name="Trade Deadline", 
                phase=SeasonPhase.TRADE_DEADLINE,
                description="NHL Trade Deadline - final day for trades",
                action=self._trade_deadline,
                is_critical=True
            ),
            SeasonMilestone(
                date=date(year + 1, 4, 1),
                name="Playoff Push",
                phase=SeasonPhase.PLAYOFF_PUSH,
                description="Final stretch - playoff positioning critical",
                action=self._playoff_push
            ),
            SeasonMilestone(
                date=date(year + 1, 4, 15),
                name="Regular Season End",
                phase=SeasonPhase.PLAYOFFS,
                description="Regular season complete - playoff seeding finalized",
                action=self._regular_season_end,
                is_critical=True
            ),
            SeasonMilestone(
                date=date(year + 1, 6, 1),
                name="Stanley Cup Finals",
                phase=SeasonPhase.PLAYOFFS,
                description="Stanley Cup Finals begin",
                action=self._stanley_cup_finals
            ),
            SeasonMilestone(
                date=date(year + 1, 6, 23),
                name="NHL Entry Draft",
                phase=SeasonPhase.ENTRY_DRAFT,
                description="Annual NHL Entry Draft",
                action=self._entry_draft,
                is_critical=True
            ),
            SeasonMilestone(
                date=date(year + 1, 7, 1),
                name="Free Agency Opens",
                phase=SeasonPhase.FREE_AGENCY,
                description="Unrestricted Free Agency period begins",
                action=self._free_agency_opens,
                is_critical=True
            ),
            SeasonMilestone(
                date=date(year + 1, 9, 1),
                name="Training Camp",
                phase=SeasonPhase.PRE_SEASON,
                description="Training camps open - new season preparation",
                action=self._training_camp_opens
            ),
            SeasonMilestone(
                date=date(year + 1, 10, 1),
                name="New Season Begins",
                phase=SeasonPhase.REGULAR_SEASON,
                description="New NHL season begins",
                action=self._new_season_begins,
                is_critical=True
            )
        ])
        
        # Sort milestones by date
        self.milestones.sort(key=lambda m: m.date)
        
    def update_season_phase(self):
        """Update the current season phase based on the date"""
        current_date = self.game_manager.current_date
        
        # Determine current phase
        old_phase = self.current_phase
        
        if current_date.month >= 10 or current_date.month <= 4:
            if current_date.month == 3:
                self.current_phase = SeasonPhase.TRADE_DEADLINE
            elif current_date.month == 4 and current_date.day >= 15:
                self.current_phase = SeasonPhase.PLAYOFFS
            else:
                self.current_phase = SeasonPhase.REGULAR_SEASON
        elif current_date.month == 6 and current_date.day >= 20:
            self.current_phase = SeasonPhase.ENTRY_DRAFT
        elif current_date.month == 7:
            self.current_phase = SeasonPhase.FREE_AGENCY  
        elif current_date.month in [8, 9]:
            self.current_phase = SeasonPhase.OFF_SEASON
        else:
            self.current_phase = SeasonPhase.OFF_SEASON
            
        # If phase changed, notify
        if old_phase != self.current_phase:
            self._on_phase_change(old_phase, self.current_phase)
            
        return self.current_phase
        
    def check_upcoming_milestones(self, days_ahead=7) -> List[SeasonMilestone]:
        """Check for upcoming milestones within the next X days"""
        current_date = self.game_manager.current_date
        future_date = current_date + timedelta(days=days_ahead)
        
        upcoming = []
        for milestone in self.milestones:
            if current_date <= milestone.date <= future_date:
                upcoming.append(milestone)
                
        return upcoming
        
    def get_next_milestone(self) -> Optional[SeasonMilestone]:
        """Get the next upcoming milestone"""
        current_date = self.game_manager.current_date
        
        for milestone in self.milestones:
            if milestone.date > current_date:
                return milestone
                
        return None
        
    def should_auto_advance(self) -> bool:
        """Determine if we should automatically advance to the next day"""
        if self.settings.mode == AutoAdvanceMode.MANUAL:
            return False
            
        current_date = self.game_manager.current_date
        
        # Check for upcoming critical milestones
        if self.settings.pause_at_milestones:
            upcoming = self.check_upcoming_milestones(1)  # Check tomorrow
            if any(m.is_critical for m in upcoming):
                return False
                
        # Check for user team games
        if self.settings.pause_at_user_games:
            todays_games = self._get_todays_games()
            user_team_games = [g for g in todays_games if self._is_user_team_game(g)]
            if user_team_games:
                return False
                
        # Check mode-specific logic
        if self.settings.mode == AutoAdvanceMode.AUTO_NON_GAME:
            # Only advance if no games today
            todays_games = self._get_todays_games()
            return len(todays_games) == 0
            
        elif self.settings.mode == AutoAdvanceMode.AUTO_TO_NEXT_GAME:
            # Keep advancing until we hit a user team game
            upcoming_user_games = self._get_upcoming_user_games(14)  # Look 2 weeks ahead
            return len(upcoming_user_games) > 0
            
        elif self.settings.mode == AutoAdvanceMode.AUTO_TO_MILESTONE:
            # Keep advancing until we hit a milestone
            next_milestone = self.get_next_milestone()
            return next_milestone is not None
            
        elif self.settings.mode == AutoAdvanceMode.FULL_AUTO:
            return True
            
        return False
        
    def start_automation(self):
        """Start automated season progression"""
        if self.automation_active:
            return
            
        self.automation_active = True
        self._automation_loop()
        
    def stop_automation(self):
        """Stop automated season progression"""
        self.automation_active = False
        
    def _automation_loop(self):
        """Main automation loop - runs continuously when automation is active"""
        if not self.automation_active:
            return
            
        try:
            # Check if we should advance
            if self.should_auto_advance():
                # Simulate the day
                self.game_manager._bulk_simming = True
                try:
                    self.game_manager.simulate_day()
                finally:
                    self.game_manager._bulk_simming = False
                
                # Update phase
                self.update_season_phase()
                
                # Check for milestones
                self._check_milestone_triggers()
                
            # Schedule next check based on speed setting
            delay_ms = int(1000 / self.settings.days_per_second)
            self.game_manager.after(delay_ms, self._automation_loop)
            
        except Exception as e:
            print(f"Error in automation loop: {e}")
            self.stop_automation()
            
    def _get_todays_games(self):
        """Get all games scheduled for today"""
        current_date = self.game_manager.current_date
        return [game for game in self.game_manager.league.schedule if game[0] == current_date]
        
    def _get_upcoming_user_games(self, days_ahead=14):
        """Get upcoming user team games within X days"""
        current_date = self.game_manager.current_date
        future_date = current_date + timedelta(days=days_ahead)
        
        user_games = []
        for game in self.game_manager.league.schedule:
            game_date, home_team, away_team = game
            if current_date < game_date <= future_date:
                if self._is_user_team_game(game):
                    user_games.append(game)
                    
        return user_games
        
    def _is_user_team_game(self, game):
        """Check if a game involves the user team"""
        _, home_team, away_team = game
        user_team = getattr(self.game_manager, 'user_team', None)
        
        if not user_team:
            return False
            
        return (home_team == user_team or away_team == user_team or
                home_team.team_name == user_team.team_name or
                away_team.team_name == user_team.team_name)
        
    def _check_milestone_triggers(self):
        """Check if any milestones should be triggered today"""
        current_date = self.game_manager.current_date
        
        for milestone in self.milestones:
            if milestone.date == current_date:
                self._trigger_milestone(milestone)
                
    def _trigger_milestone(self, milestone):
        """Trigger a milestone event"""
        print(f"🎯 MILESTONE: {milestone.name}")
        print(f"📅 Date: {milestone.date}")
        print(f"📝 Description: {milestone.description}")
        
        # Execute milestone action if available
        if milestone.action:
            try:
                milestone.action()
            except Exception as e:
                print(f"Error executing milestone action: {e}")
                
        # Pause automation for critical milestones
        if milestone.is_critical and self.automation_active:
            self.stop_automation()
            self._show_milestone_notification(milestone)
            
    def _show_milestone_notification(self, milestone):
        """Show notification for important milestones"""
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            messagebox.showinfo(
                f"Season Milestone: {milestone.name}",
                f"📅 {milestone.date.strftime('%B %d, %Y')}\n\n"
                f"🏒 {milestone.description}\n\n"
                f"The automated season progression has been paused.\n"
                f"Review the situation and continue when ready."
            )
            
        except Exception as e:
            print(f"Error showing milestone notification: {e}")
            
    def _on_phase_change(self, old_phase, new_phase):
        """Handle season phase changes"""
        print(f"📈 SEASON PHASE CHANGE: {old_phase.value} → {new_phase.value}")
        
        # Add phase-specific logic here
        if new_phase == SeasonPhase.TRADE_DEADLINE:
            self._enter_trade_deadline_period()
        elif new_phase == SeasonPhase.PLAYOFFS:
            self._enter_playoffs()
        elif new_phase == SeasonPhase.FREE_AGENCY:
            self._enter_free_agency()
            
    # Milestone Action Methods
    def _november_checkin(self):
        """November season assessment"""
        # Analyze team performance and generate reports
        print("📊 November Check-in: Evaluating team performance...")
        
    def _christmas_break(self):
        """Christmas holiday break"""
        print("🎄 Christmas Break: Holiday roster freeze in effect...")
        
    def _new_year_milestone(self):
        """New Year milestone"""
        print("🎊 Happy New Year! Second half of season begins...")
        
    def _february_push(self):
        """February trade deadline approach"""
        print("📈 February Push: Trade deadline approaches, teams making moves...")
        
    def _trade_deadline(self):
        """Trade deadline day"""
        print("⏰ TRADE DEADLINE: Final day for trades!")
        
    def _playoff_push(self):
        """Final playoff push"""
        print("🏒 Playoff Push: Every game matters now!")
        
    def _regular_season_end(self):
        """Regular season completion"""
        print("🏁 Regular Season Complete: Playoff seeding finalized!")
        
    def _stanley_cup_finals(self):
        """Stanley Cup Finals"""
        print("🏆 Stanley Cup Finals: The ultimate prize awaits!")
        
    def _entry_draft(self):
        """Entry draft day"""
        print("📋 Entry Draft: Building the future!")
        
    def _free_agency_opens(self):
        """Free agency period begins"""
        print("💰 Free Agency Opens: Player movement begins!")
        
    def _training_camp_opens(self):
        """Training camps open"""
        print("🏒 Training Camps Open: New season preparation begins!")
        
    def _new_season_begins(self):
        """New season starts"""
        print("🚀 New Season Begins: Fresh start for all teams!")
        
    def _enter_trade_deadline_period(self):
        """Enter trade deadline period"""
        print("📈 Entering Trade Deadline Period...")
        
    def _enter_playoffs(self):
        """Enter playoff period"""
        print("🏒 Playoffs Begin!")
        
    def _enter_free_agency(self):
        """Enter free agency period"""
        print("💰 Free Agency Period Active!")

# Utility functions for integration with main game
def get_season_phase_color(phase: SeasonPhase) -> str:
    """Get color code for season phase"""
    colors = {
        SeasonPhase.PRE_SEASON: "#4CAF50",      # Green
        SeasonPhase.REGULAR_SEASON: "#2196F3",  # Blue  
        SeasonPhase.TRADE_DEADLINE: "#FF9800",  # Orange
        SeasonPhase.PLAYOFF_PUSH: "#FF5722",    # Deep Orange
        SeasonPhase.PLAYOFFS: "#9C27B0",        # Purple
        SeasonPhase.DRAFT_LOTTERY: "#607D8B",   # Blue Grey
        SeasonPhase.ENTRY_DRAFT: "#795548",     # Brown
        SeasonPhase.FREE_AGENCY: "#009688",     # Teal
        SeasonPhase.OFF_SEASON: "#757575",      # Grey
    }
    return colors.get(phase, "#000000")

def format_days_until_milestone(milestone: SeasonMilestone, current_date: date) -> str:
    """Format days until milestone for display"""
    days = (milestone.date - current_date).days
    
    if days == 0:
        return "Today"
    elif days == 1:
        return "Tomorrow"
    elif days < 7:
        return f"{days} days"
    elif days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''}"
    else:
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''}"
