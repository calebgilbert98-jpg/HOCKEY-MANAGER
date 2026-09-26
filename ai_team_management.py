"""
Phase 2B Test Script: AI Team Management System
Next step in Phase 2 implementation - Intelligent CPU team behaviors
"""

import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
from datetime import date, timedelta
from game_classes import Player, Team, PlayerPosition, Contract
from salary_cap_system import SalaryCapSystem, DEFAULT_CAP


class ManagementPriority(Enum):
    """AI management priorities"""
    REBUILD = "rebuild"
    CONTEND = "contend"
    MAINTAIN = "maintain"
    DEVELOP = "develop"


class TradePreference(Enum):
    """Trade willingness levels"""
    AGGRESSIVE = "aggressive"
    MODERATE = "moderate"
    CONSERVATIVE = "conservative"
    INACTIVE = "inactive"


@dataclass
class TeamStrategy:
    """AI team management strategy"""
    priority: ManagementPriority
    trade_preference: TradePreference
    budget_limit: int
    min_roster_age: int
    max_roster_age: int
    position_needs: List[PlayerPosition]
    salary_cap_tolerance: float  # 0.0 to 1.0
    
    # Strategic preferences
    prefer_youth: bool
    prefer_experience: bool
    risk_tolerance: float  # 0.0 to 1.0
    
    # Trading preferences
    will_trade_picks: bool
    will_trade_prospects: bool
    rebuilding_timeline: int  # years


@dataclass
class AIDecision:
    """Represents an AI management decision"""
    team_name: str
    decision_type: str
    target_player: Optional[Player]
    offer_details: Dict
    priority_score: float
    reasoning: str
    timestamp: date


class AITeamManager:
    """
    Advanced AI system for managing CPU teams
    Handles roster decisions, trades, free agency, contract negotiations
    """
    
    def __init__(self):
        self.team_strategies: Dict[str, TeamStrategy] = {}
        self.decision_history: List[AIDecision] = []
        self._cap_system: Optional[SalaryCapSystem] = None
        self.trade_offers: List[Dict] = []
        self.free_agency_targets: Dict[str, List[Player]] = {}
        
        # Decision-making parameters
        self.decision_frequency = 7  # Check every 7 days
        self.last_decision_date = date.today()
        
        # Market analysis cache
        self.player_values: Dict[str, int] = {}
        self.position_demand: Dict[PlayerPosition, float] = {}

    def set_cap_system(self, cap_system: Optional[SalaryCapSystem],
                       league=None):
        """Attach the league's salary cap system for cap-relative demands."""
        self._cap_system = cap_system
        self._league_ref = league

    def initialize_team_strategies(self, teams: List[Team]):
        """Initialize AI strategies for all CPU teams"""
        for team in teams:
            if getattr(team, 'is_user_team', False):  # Skip user team
                continue

            strategy = self._generate_team_strategy(team)
            self.team_strategies[team.team_name] = strategy
            
            print(f"AI Strategy for {team.team_name}:")
            print(f"  Priority: {strategy.priority.value}")
            print(f"  Trade Preference: {strategy.trade_preference.value}")
            print(f"  Position Needs: {[pos.value for pos in strategy.position_needs]}")
            print(f"  Prefer Youth: {strategy.prefer_youth}")
            print()
    
    def _generate_team_strategy(self, team: Team) -> TeamStrategy:
        """Generate appropriate strategy based on team composition"""
        # Analyze current roster
        roster_analysis = self._analyze_roster(team)
        
        # Determine management priority
        if roster_analysis['avg_age'] > 30 and roster_analysis['avg_overall'] < 75:
            priority = ManagementPriority.REBUILD
            trade_pref = TradePreference.AGGRESSIVE
            prefer_youth = True
            prefer_experience = False
        elif roster_analysis['avg_overall'] > 80:
            priority = ManagementPriority.CONTEND
            trade_pref = TradePreference.MODERATE
            prefer_youth = False
            prefer_experience = True
        elif roster_analysis['avg_age'] < 25:
            priority = ManagementPriority.DEVELOP
            trade_pref = TradePreference.CONSERVATIVE
            prefer_youth = True
            prefer_experience = False
        else:
            priority = ManagementPriority.MAINTAIN
            trade_pref = TradePreference.MODERATE
            prefer_youth = random.choice([True, False])
            prefer_experience = not prefer_youth
        
        # Identify position needs
        position_needs = self._identify_position_needs(team)
        
        return TeamStrategy(
            priority=priority,
            trade_preference=trade_pref,
            budget_limit=random.randint(60_000_000, 85_000_000),
            min_roster_age=18 if prefer_youth else 23,
            max_roster_age=30 if prefer_youth else 37,
            position_needs=position_needs,
            salary_cap_tolerance=random.uniform(0.8, 0.95),
            prefer_youth=prefer_youth,
            prefer_experience=prefer_experience,
            risk_tolerance=random.uniform(0.2, 0.8),
            will_trade_picks=priority != ManagementPriority.REBUILD,
            will_trade_prospects=priority == ManagementPriority.CONTEND,
            rebuilding_timeline=random.randint(2, 5) if priority == ManagementPriority.REBUILD else 0
        )
    
    def _analyze_roster(self, team: Team) -> Dict:
        """Analyze team roster composition"""
        if not hasattr(team, 'roster') or not team.roster:
            return {
                'avg_age': 25,
                'avg_overall': 70,
                'total_salary': 50_000_000,
                'position_balance': 0.5
            }
        
        total_age = sum(player.age for player in team.roster)
        total_overall = sum(player.overall_rating() for player in team.roster)
        total_salary = sum(getattr(player, 'salary', 750000) for player in team.roster)
        
        return {
            'avg_age': total_age / len(team.roster),
            'avg_overall': total_overall / len(team.roster),
            'total_salary': total_salary,
            'roster_size': len(team.roster),
            'position_balance': self._calculate_position_balance(team.roster)
        }
    
    def _calculate_position_balance(self, roster: List[Player]) -> float:
        """Calculate how balanced the roster positions are"""
        position_counts = {}
        for player in roster:
            pos = player.primary_position
            position_counts[pos] = position_counts.get(pos, 0) + 1
        
        # Ideal distribution: ~12F, 6D, 2G out of 20 players
        ideal_ratios = {
            PlayerPosition.CENTER: 4,
            PlayerPosition.LEFT_WING: 4, 
            PlayerPosition.RIGHT_WING: 4,
            PlayerPosition.DEFENSE: 6,
            PlayerPosition.GOALIE: 2
        }
        
        balance_score = 0
        for pos, ideal_count in ideal_ratios.items():
            actual_count = sum(1 for p in roster if p.primary_position == pos)
            ratio = min(actual_count / ideal_count, ideal_count / max(actual_count, 1))
            balance_score += ratio
        
        return balance_score / len(ideal_ratios)
    
    def _identify_position_needs(self, team: Team) -> List[PlayerPosition]:
        """Identify which positions the team needs to address"""
        if not hasattr(team, 'roster') or not team.roster:
            return []
        
        position_counts = {}
        position_quality = {}
        
        for player in team.roster:
            pos = player.primary_position
            position_counts[pos] = position_counts.get(pos, 0) + 1
            
            if pos not in position_quality:
                position_quality[pos] = []
            position_quality[pos].append(player.overall_rating())
        
        needs = []
        
        # Check for quantity needs
        if position_counts.get(PlayerPosition.CENTER, 0) < 3:
            needs.append(PlayerPosition.CENTER)
        if position_counts.get(PlayerPosition.LEFT_WING, 0) < 3:
            needs.append(PlayerPosition.LEFT_WING)
        if position_counts.get(PlayerPosition.RIGHT_WING, 0) < 3:
            needs.append(PlayerPosition.RIGHT_WING)
        if position_counts.get(PlayerPosition.DEFENSE, 0) < 5:
            needs.append(PlayerPosition.DEFENSE)
        if position_counts.get(PlayerPosition.GOALIE, 0) < 2:
            needs.append(PlayerPosition.GOALIE)
        
        # Check for quality needs (average rating below 70)
        for pos, ratings in position_quality.items():
            if ratings and sum(ratings) / len(ratings) < 70:
                if pos not in needs:
                    needs.append(pos)
        
        return needs
    
    def process_daily_decisions(self, teams: List[Team], free_agents: List[Player], 
                               current_date: date) -> List[AIDecision]:
        """Process daily AI management decisions for all teams"""
        decisions = []
        
        # Only make decisions every few days
        if (current_date - self.last_decision_date).days < self.decision_frequency:
            return decisions
        
        for team in teams:
            if getattr(team, 'is_user_team', False):
                continue

            strategy = self.team_strategies.get(team.team_name)
            if not strategy:
                continue
            
            # Check for various decision types
            team_decisions = []
            
            # 1. Free agency decisions
            fa_decisions = self._evaluate_free_agency(team, strategy, free_agents, current_date)
            team_decisions.extend(fa_decisions)
            
            # 2. Trade decisions
            trade_decisions = self._evaluate_trades(team, strategy, teams, current_date)
            team_decisions.extend(trade_decisions)
            
            # 3. Roster management
            roster_decisions = self._evaluate_roster_moves(team, strategy, current_date)
            team_decisions.extend(roster_decisions)
            
            # 4. Contract extensions
            contract_decisions = self._evaluate_contract_extensions(team, strategy, current_date)
            team_decisions.extend(contract_decisions)
            
            decisions.extend(team_decisions)
        
        self.last_decision_date = current_date
        self.decision_history.extend(decisions)
        
        return decisions
    
    def _evaluate_free_agency(self, team: Team, strategy: TeamStrategy,
                             free_agents: List[Player], current_date: date) -> List[AIDecision]:
        """Evaluate free agent signings for a team"""
        decisions = []
        
        if not strategy.position_needs or not free_agents:
            return decisions
        
        # Calculate available budget
        current_salary = sum(getattr(p, 'salary', 750000) for p in team.roster)
        available_budget = strategy.budget_limit - current_salary
        
        if available_budget < 1_000_000:  # Need at least 1M available
            return decisions
        
        # Find suitable free agents
        suitable_fas = []
        for fa in free_agents:
            if fa.primary_position in strategy.position_needs:
                # Check age preference
                if strategy.prefer_youth and fa.age > strategy.max_roster_age:
                    continue
                if strategy.prefer_experience and fa.age < strategy.min_roster_age:
                    continue
                
                # Estimate salary demand
                estimated_salary = self._estimate_player_salary(fa)
                if estimated_salary <= available_budget:
                    suitable_fas.append((fa, estimated_salary))
        
        # Sort by priority (overall rating vs cost)
        suitable_fas.sort(key=lambda x: x[0].overall_rating() / (x[1] / 1_000_000), reverse=True)
        
        # Make offers to top candidates
        for fa, estimated_salary in suitable_fas[:3]:  # Top 3 candidates
            priority_score = self._calculate_fa_priority(fa, strategy, team)
            
            if priority_score > 0.6:  # High interest threshold
                decision = AIDecision(
                    team_name=team.team_name,
                    decision_type="free_agent_offer",
                    target_player=fa,
                    offer_details={
                        "salary": estimated_salary,
                        "term": self._determine_contract_length(fa, strategy),
                        "no_trade_clause": fa.overall_rating() > 85
                    },
                    priority_score=priority_score,
                    reasoning=f"Addresses {fa.primary_position.value} need, fits strategy",
                    timestamp=current_date
                )
                decisions.append(decision)
        
        return decisions
    
    def _evaluate_trades(self, team: Team, strategy: TeamStrategy,
                        all_teams: List[Team], current_date: date) -> List[AIDecision]:
        """Evaluate potential trades for a team"""
        decisions = []
        
        if strategy.trade_preference == TradePreference.INACTIVE:
            return decisions
        
        # Look for trade opportunities based on strategy
        if strategy.priority == ManagementPriority.REBUILD:
            # Look to trade veterans for picks/prospects
            veterans = [p for p in team.roster if p.age > 28 and p.overall_rating() > 75]
            for veteran in veterans[:2]:  # Limit trade attempts
                trade_decision = self._create_veteran_trade_offer(veteran, team, strategy, current_date)
                if trade_decision:
                    decisions.append(trade_decision)
        
        elif strategy.priority == ManagementPriority.CONTEND:
            # Look to acquire impact players
            if strategy.position_needs:
                target_decision = self._create_acquisition_offer(team, strategy, all_teams, current_date)
                if target_decision:
                    decisions.append(target_decision)
        
        return decisions
    
    def _evaluate_roster_moves(self, team: Team, strategy: TeamStrategy,
                              current_date: date) -> List[AIDecision]:
        """Evaluate internal roster moves (call-ups, send-downs)"""
        decisions = []
        
        if not hasattr(team, 'ahl_roster') or not hasattr(team, 'prospects'):
            return decisions
        
        # Look for prospects ready for promotion
        if hasattr(team, 'prospects'):
            ready_prospects = [p for p in team.prospects 
                             if p.age >= 20 and p.overall_rating() > 70]
            
            for prospect in ready_prospects[:2]:  # Limit promotions
                decision = AIDecision(
                    team_name=team.team_name,
                    decision_type="promote_prospect",
                    target_player=prospect,
                    offer_details={"from": "prospects", "to": "ahl_roster"},
                    priority_score=0.7,
                    reasoning=f"Prospect ready for AHL promotion",
                    timestamp=current_date
                )
                decisions.append(decision)
        
        return decisions
    
    def _evaluate_contract_extensions(self, team: Team, strategy: TeamStrategy,
                                    current_date: date) -> List[AIDecision]:
        """Evaluate contract extension opportunities"""
        decisions = []
        
        # Find players with expiring contracts
        expiring_players = []
        for player in team.roster:
            if hasattr(player, 'contract') and player.contract:
                # Assume contract expires next year for testing
                if random.random() < 0.1:  # 10% chance of expiring contract
                    expiring_players.append(player)
        
        for player in expiring_players:
            # Decide whether to extend based on strategy
            should_extend = self._should_extend_player(player, strategy)
            
            if should_extend:
                decision = AIDecision(
                    team_name=team.team_name,
                    decision_type="contract_extension",
                    target_player=player,
                    offer_details={
                        "salary": self._estimate_player_salary(player),
                        "term": self._determine_contract_length(player, strategy)
                    },
                    priority_score=0.8,
                    reasoning=f"Key player fitting strategy",
                    timestamp=current_date
                )
                decisions.append(decision)
        
        return decisions
    
    def _estimate_player_salary(self, player: Player) -> int:
        """Estimate fair market salary for a player.

        Demands are expressed as a % of the salary cap, so they scale
        automatically as the cap grows. Market-setter premiums apply.
        """
        cap_sys = self._cap_system
        cap = cap_sys.current_cap if cap_sys else DEFAULT_CAP

        ovr = player.overall_rating()  # internal ~50 scale
        # Convert to 1-100 display scale for market logic
        try:
            from game_classes import to_100_scale
            ovr100 = int(to_100_scale(ovr))
        except Exception:
            ovr100 = int(ovr * 2)

        # Base demand as % of cap: ~100k per OVR point at $83.5M cap
        # = ovr * 100_000 / 83_500_000 ≈ ovr * 0.0012 (0.12% per point)
        base_cap_pct = (ovr * 100_000) / DEFAULT_CAP

        # Age adjustments (multiplicative on the cap %)
        if player.age < 25:
            base_cap_pct *= 0.8
        elif player.age > 32:
            base_cap_pct *= 0.6

        # Position adjustments
        pos = player.primary_position
        pos_name = pos.value if hasattr(pos, "value") else str(pos)
        if pos == PlayerPosition.GOALIE:
            base_cap_pct *= 1.2
        elif pos == PlayerPosition.CENTER:
            base_cap_pct *= 1.1

        # Convert to dollars at CURRENT cap, apply market premium
        if cap_sys:
            league = getattr(self, "_league_ref", None)
            season = getattr(league, "season_year", 0) if league else 0
            salary = cap_sys.demand_for(base_cap_pct, ovr100, pos_name,
                                        player.age, season)
        else:
            salary = int(base_cap_pct * cap)

        # Clamp: league min to 20% of cap (NHL max)
        return max(min(int(salary), int(cap * 0.20)), 750_000)
    
    def _determine_contract_length(self, player: Player, strategy: TeamStrategy) -> int:
        """Determine appropriate contract length"""
        if player.age < 26:
            return random.randint(2, 5)  # Bridge or long-term for youth
        elif player.age < 30:
            return random.randint(3, 7)  # Prime years
        else:
            return random.randint(1, 3)  # Short term for veterans
    
    def _calculate_fa_priority(self, player: Player, strategy: TeamStrategy, team: Team) -> float:
        """Calculate how much a team wants a free agent"""
        priority = 0.0
        
        # Position need bonus
        if player.primary_position in strategy.position_needs:
            priority += 0.4
        
        # Overall rating bonus
        priority += min(player.overall_rating() / 170, 0.3)  # 51 OVR -> full 0.3
        
        # Age preference
        if strategy.prefer_youth and player.age < 26:
            priority += 0.2
        elif strategy.prefer_experience and player.age > 28:
            priority += 0.2
        
        # Strategic fit
        if strategy.priority == ManagementPriority.CONTEND and player.overall_rating() > 85:
            priority += 0.2
        elif strategy.priority == ManagementPriority.REBUILD and player.age < 24:
            priority += 0.2
        
        return min(priority, 1.0)
    
    def _should_extend_player(self, player: Player, strategy: TeamStrategy) -> bool:
        """Determine if a player should be extended"""
        # Core players (high overall) should usually be extended
        if player.overall_rating() > 85:
            return True
        
        # Age considerations
        if strategy.prefer_youth and player.age > 30:
            return False
        if strategy.prefer_experience and player.age < 23:
            return False
        
        # Strategic fit
        if strategy.priority == ManagementPriority.REBUILD:
            return player.age < 26  # Only extend young players
        elif strategy.priority == ManagementPriority.CONTEND:
            return player.overall_rating() > 40  # Extend quality players
        
        return player.overall_rating() > 37  # Default threshold
    
    def _create_veteran_trade_offer(self, veteran: Player, team: Team, 
                                  strategy: TeamStrategy, current_date: date) -> Optional[AIDecision]:
        """Create a trade offer for a veteran player"""
        if strategy.trade_preference == TradePreference.CONSERVATIVE:
            return None
        
        return AIDecision(
            team_name=team.team_name,
            decision_type="trade_offer_veteran",
            target_player=veteran,
            offer_details={
                "seeking": "picks_prospects",
                "willingness": strategy.trade_preference.value
            },
            priority_score=0.7,
            reasoning=f"Rebuilding - trading veteran for future assets",
            timestamp=current_date
        )
    
    def _create_acquisition_offer(self, team: Team, strategy: TeamStrategy,
                                all_teams: List[Team], current_date: date) -> Optional[AIDecision]:
        """Create an offer to acquire a needed player"""
        if not strategy.position_needs:
            return None
        
        target_position = strategy.position_needs[0]
        
        return AIDecision(
            team_name=team.team_name,
            decision_type="trade_seek_player",
            target_player=None,  # Will be determined by trade logic
            offer_details={
                "position_needed": target_position.value,
                "max_salary": strategy.budget_limit * 0.15,  # 15% of budget max
                "assets_available": "picks_prospects_players"
            },
            priority_score=0.8,
            reasoning=f"Contending - need {target_position.value}",
            timestamp=current_date
        )
    
    def get_team_strategy(self, team_name: str) -> Optional[TeamStrategy]:
        """Get the AI strategy for a specific team"""
        return self.team_strategies.get(team_name)
    
    def get_recent_decisions(self, team_name: str = None, days: int = 30) -> List[AIDecision]:
        """Get recent AI decisions, optionally filtered by team"""
        cutoff_date = date.today() - timedelta(days=days)
        
        recent = [d for d in self.decision_history if d.timestamp >= cutoff_date]
        
        if team_name:
            recent = [d for d in recent if d.team_name == team_name]
        
        return recent


def test_ai_system():
    """Test the AI team management system"""
    print("🤖 Testing AI Team Management System...")
    print("=" * 60)
    
    # Create test teams
    from game_classes import Team
    
    test_teams = []
    team_names = ["Boston Bruins", "Buffalo Sabres", "Montreal Canadiens", "Toronto Maple Leafs"]
    
    for name in team_names:
        team = Team(name, "Eastern", "Atlantic", "Test Division")
        
        # Create test roster
        team.roster = []
        for i in range(20):
            pos_options = [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING,
                          PlayerPosition.DEFENSE, PlayerPosition.GOALIE]
            weights = [4, 4, 4, 6, 2] if i < 20 else [1, 1, 1, 1, 1]
            
            player = Player(
                first_name=f"Test{i}",
                last_name=f"Player{i}",
                age=random.randint(18, 38),
                primary_position=random.choices(pos_options, weights=weights)[0]
            )
            
            # Set some basic attributes for overall rating calculation
            for attr in ['skating', 'shooting', 'passing', 'checking', 'defense', 'hockey_iq']:
                setattr(player, attr, random.randint(60, 95))
            
            team.roster.append(player)
        
        team.ahl_roster = []
        team.prospects = []
        test_teams.append(team)
    
    # Test AI system
    ai_manager = AITeamManager()
    
    print("📋 Initializing team strategies...")
    ai_manager.initialize_team_strategies(test_teams)
    
    print("\n🔄 Processing daily decisions...")
    current_date = date.today()
    
    # Create some test free agents
    free_agents = []
    for i in range(10):
        fa = Player(
            first_name=f"Free",
            last_name=f"Agent{i}",
            age=random.randint(22, 34),
            primary_position=random.choice(list(PlayerPosition))
        )
        for attr in ['skating', 'shooting', 'passing', 'checking', 'defense', 'hockey_iq']:
            setattr(fa, attr, random.randint(65, 90))
        free_agents.append(fa)
    
    decisions = ai_manager.process_daily_decisions(test_teams, free_agents, current_date)
    
    print(f"\n📊 AI made {len(decisions)} decisions:")
    for decision in decisions:
        print(f"  {decision.team_name}: {decision.decision_type}")
        if decision.target_player:
            print(f"    Target: {decision.target_player.full_name} ({decision.target_player.primary_position.value})")
        print(f"    Reasoning: {decision.reasoning}")
        print(f"    Priority Score: {decision.priority_score:.2f}")
        print()
    
    print("✅ AI Team Management System test complete!")
    
    # Test strategy retrieval
    print("\n📈 Sample Team Strategy (Buffalo Sabres):")
    strategy = ai_manager.get_team_strategy("Buffalo Sabres")
    if strategy:
        print(f"  Priority: {strategy.priority.value}")
        print(f"  Trade Preference: {strategy.trade_preference.value}")
        print(f"  Budget Limit: ${strategy.budget_limit:,}")
        print(f"  Position Needs: {[pos.value for pos in strategy.position_needs]}")
        print(f"  Prefer Youth: {strategy.prefer_youth}")
        print(f"  Risk Tolerance: {strategy.risk_tolerance:.2f}")
    
    return ai_manager


if __name__ == "__main__":
    test_ai_system()
