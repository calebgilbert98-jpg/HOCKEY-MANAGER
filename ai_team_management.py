"""
Phase 2B Test Script: AI Team Management System
Next step in Phase 2 implementation - Intelligent CPU team behaviors
"""

import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
from datetime import date, timedelta
from game_classes import Player, Team, PlayerPosition, Contract, StaffRole, is_human_managed
from salary_cap_system import SalaryCapSystem, DEFAULT_CAP

from ai_gm_identity import (
    GMIdentity, GMJobSecurity, gm_identity_from_staff, update_job_security,
    compute_risk_appetite, signing_urgency, expectation_from_strength,
)


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

        # GM identity layer: who runs each AI club, and how safe his job is.
        # Strategies are derived from these, not rolled randomly.
        self.gm_identities: Dict[str, GMIdentity] = {}
        self.gm_security: Dict[str, GMJobSecurity] = {}
        self._sec_flags: Dict[str, Tuple[bool, bool, bool]] = {}  # team -> (hot_seat, tenured_winner, owner_warning)
        
        # Decision-making parameters
        self.decision_frequency = 7  # Check every 7 days
        self.last_decision_date = date.today()

        # Stories queued by AI signings (signing, market-setter, contract
        # fallout). The app flushes these into the news feed; the manager
        # holds no app ref.
        self._pending_news: List[str] = []
        
        # Market analysis cache
        self.player_values: Dict[str, int] = {}
        self.position_demand: Dict[PlayerPosition, float] = {}

        # Extension forward books, rebuilt per team each decision pass:
        # team_name -> ai_extension_planning.ExtensionPlan. Shared by the
        # extension queue and the UFA market so reserved core money is
        # never spent twice.
        self._ext_plans: Dict[str, Any] = {}

    def set_cap_system(self, cap_system: Optional[SalaryCapSystem],
                       league=None):
        """Attach the league's salary cap system for cap-relative demands."""
        self._cap_system = cap_system
        self._league_ref = league

    def drain_pending_news(self) -> List[str]:
        """Stories queued by AI signings. The app flushes these into the
        news feed with today's date."""
        try:
            pend = getattr(self, "_pending_news", None)
            self._pending_news = []
            return list(pend) if isinstance(pend, list) else []
        except Exception:
            return []

    def _team_gm(self, team: Team):
        """Return the team's General Manager staff member, if any."""
        try:
            for s in getattr(team, "staff", []) or []:
                if getattr(s, "role", None) == StaffRole.GENERAL_MANAGER:
                    return s
        except Exception:
            pass
        return None

    def initialize_team_strategies(self, teams: List[Team]):
        """Initialize AI strategies for all CPU teams"""
        for team in teams:
            if is_human_managed(team):  # Skip human clubs (local + MP clients)
                continue

            # Identity first: the strategy describes THIS GM, not a random one.
            identity = gm_identity_from_staff(team.team_name, self._team_gm(team))
            self.gm_identities[team.team_name] = identity
            roster_analysis = self._analyze_roster(team)
            sec = GMJobSecurity(
                team_name=team.team_name,
                expectation=expectation_from_strength(roster_analysis["avg_overall"]),
            )
            self.gm_security[team.team_name] = sec
            self._sec_flags[team.team_name] = (sec.hot_seat, sec.tenured_winner,
                                               sec.owner_warning)

            strategy = self._generate_team_strategy(team, identity, sec,
                                                    roster_analysis)
            self.team_strategies[team.team_name] = strategy

            print(f"AI Strategy for {team.team_name}:")
            print(f"  GM: {identity.describe()}")
            print(f"  Board: {sec.describe()}")
            print(f"  Priority: {strategy.priority.value}")
            print(f"  Trade Preference: {strategy.trade_preference.value}")
            print(f"  Position Needs: {[pos.value for pos in strategy.position_needs]}")
            print(f"  Prefer Youth: {strategy.prefer_youth}")
            print()

    def _generate_team_strategy(self, team: Team, identity: Optional[GMIdentity] = None,
                                sec: Optional[GMJobSecurity] = None,
                                roster_analysis: Optional[Dict] = None) -> TeamStrategy:
        """Generate a strategy that reflects the club's actual GM.

        Roster composition sets the baseline; the GM's personality, job
        security, and recent success move it. A GM on the hot seat chases
        wins now instead of rebuilding; a tenured Cup winner stays patient.
        """
        if roster_analysis is None:
            roster_analysis = self._analyze_roster(team)
        if identity is None:
            identity = gm_identity_from_staff(team.team_name, self._team_gm(team))
        if sec is None:
            sec = self.gm_security.get(team.team_name) or GMJobSecurity(
                team_name=team.team_name,
                expectation=expectation_from_strength(roster_analysis["avg_overall"]))

        risk = compute_risk_appetite(identity, sec)

        # Determine management priority
        if roster_analysis['avg_age'] > 30 and roster_analysis['avg_overall'] < 75:
            priority = ManagementPriority.REBUILD
            prefer_youth = True
            prefer_experience = False
        elif roster_analysis['avg_overall'] > 80:
            priority = ManagementPriority.CONTEND
            prefer_youth = False
            prefer_experience = True
        elif roster_analysis['avg_age'] < 25:
            priority = ManagementPriority.DEVELOP
            prefer_youth = True
            prefer_experience = False
        else:
            priority = ManagementPriority.MAINTAIN
            # Personality breaks the tie: patient GMs develop, aggressive ones buy.
            prefer_youth = identity.patience >= 0.5
            prefer_experience = not prefer_youth

        # Job security overrides: a GM fighting for his job does not trade
        # veterans for picks, and a tenured winner does not panic-buy.
        # But the hot seat does not turn every GM into Chiarelli: only a GM
        # wired to bend under pressure (pressure_response >= 0.5) flips a
        # rebuild into win-now. A patient builder trusts his vision and
        # keeps building -- that's who he is.
        if (sec.hot_seat and not sec.owner_warning
                and identity.pressure_response >= 0.5
                and priority in (ManagementPriority.REBUILD,
                                 ManagementPriority.DEVELOP)):
            priority = ManagementPriority.CONTEND
            prefer_youth = False
            prefer_experience = True
        if sec.tenured_winner and priority == ManagementPriority.CONTEND:
            # stays contending, but patient about it (trade pref below)

            pass

        # Trade preference from the GM's aggression, nudged by job security.
        # The hot-seat nudge scales with how THIS gm handles pressure; a
        # a GM under owner warning gets reined in by the board instead of going brash.
        agg = identity.aggression \
            + (0.15 * identity.pressure_response if sec.hot_seat else 0.0) \
            - (0.15 if sec.tenured_winner else 0.0) \
            - (0.15 if sec.owner_warning else 0.0)
        if agg >= 0.65:
            trade_pref = TradePreference.AGGRESSIVE
        elif agg >= 0.45:
            trade_pref = TradePreference.MODERATE
        elif agg >= 0.30:
            trade_pref = TradePreference.CONSERVATIVE
        else:
            trade_pref = TradePreference.INACTIVE

        # Identify position needs
        position_needs = self._identify_position_needs(team)

        # Budget: aggressive / hot-seat GMs spend closer to the cap.
        cap = self._cap_system.current_cap if self._cap_system else DEFAULT_CAP
        budget_limit = int(cap * (0.82 + 0.16 * risk))

        return TeamStrategy(
            priority=priority,
            trade_preference=trade_pref,
            budget_limit=budget_limit,
            min_roster_age=18 if prefer_youth else 23,
            max_roster_age=30 if prefer_youth else 37,
            position_needs=position_needs,
            salary_cap_tolerance=0.80 + 0.15 * risk,
            prefer_youth=prefer_youth,
            prefer_experience=prefer_experience,
            risk_tolerance=risk,
            # A GM under owner warning doesn't get to mortgage anything: the board
            # vetoes pick and prospect deals on his way out.
            will_trade_picks=(priority != ManagementPriority.REBUILD
                              and not sec.owner_warning),
            # Prospects move for a contender, or for a hot-seat GM who is
            # wired to panic -- never while the owner's warning has him leashed.
            will_trade_prospects=(
                not sec.owner_warning and (
                    priority == ManagementPriority.CONTEND
                    or (sec.hot_seat and identity.pressure_response >= 0.5))),
            rebuilding_timeline=(max(2, min(5, int(round(5 - 3 * identity.patience))))
                               if priority == ManagementPriority.REBUILD else 0),
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
            if is_human_managed(team):
                continue

            strategy = self.team_strategies.get(team.team_name)
            if not strategy:
                continue

            # Weekly board review: the GM's job security moves with results,
            # and a change in seat status rewrites his strategy.
            self._weekly_board_review(team, current_date)
            strategy = self.team_strategies.get(team.team_name, strategy)
            identity = self.gm_identities.get(team.team_name)
            sec = self.gm_security.get(team.team_name)

            # Extension forward book: which pieces are due, what their
            # raises cost, what's safe to spend on everything else. Built
            # fresh each pass; the extension queue and the UFA market both
            # read it so reserved core money is never spent twice.
            try:
                self._ext_plans[team.team_name] = self._build_extension_plan(
                    team, identity, strategy, current_date)
            except Exception:
                pass

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

            # 5. Prospect signings: lock up drafted rookies to ELCs when they
            # deserve it (top talent / NHL-ready) or need it (rights expiring,
            # roster hole). A user signs his picks; the AI does too.
            if identity is not None and sec is not None:
                sign_decisions = self._evaluate_prospect_signings(
                    team, strategy, identity, sec, current_date)
                team_decisions.extend(sign_decisions)

            # Execute the decisions this manager owns end-to-end (FA
            # signings, extensions, prospect signings, gated promotions).
            # Trade offers remain proposals (they go through negotiation).
            self._execute_decisions(team, team_decisions)

            decisions.extend(team_decisions)

        self.last_decision_date = current_date
        self.decision_history.extend(decisions)

        return decisions

    def _weekly_board_review(self, team: Team, current_date: date):
        """Update the AI GM's job security from results; refresh his
        strategy if his seat status changed (hot seat <-> stable)."""
        sec = self.gm_security.get(team.team_name)
        identity = self.gm_identities.get(team.team_name)
        if sec is None or identity is None:
            return
        league = getattr(self, "_league_ref", None)
        champ = getattr(league, "_last_cup_champ", None) if league else None
        season_year = getattr(league, "season_year", current_date.year) if league else current_date.year
        try:
            season_year = int(season_year)
        except (TypeError, ValueError):
            season_year = current_date.year
        update_job_security(sec, identity, team, champ, season_year)

        if sec.gm_fired:
            # The owner carried out the threat: the old GM is gone, an
            # interim runs the club, and the seat resets to a honeymoon.
            # (The Staff member stays on the roster; the AI just stops
            # listening to him.)
            identity = gm_identity_from_staff(team.team_name, None)
            self.gm_identities[team.team_name] = identity
            sec.gm_fired = False
            sec.owner_warning = False
            sec.confidence = 55.0
            sec.hot_seat = False
            sec.tenured_winner = False
            self.team_strategies[team.team_name] = self._generate_team_strategy(
                team, identity, sec)
            self._sec_flags[team.team_name] = (sec.hot_seat,
                                               sec.tenured_winner,
                                               sec.owner_warning)
            return

        flags = (sec.hot_seat, sec.tenured_winner, sec.owner_warning)
        if self._sec_flags.get(team.team_name) != flags:
            self._sec_flags[team.team_name] = flags
            # The man managing the club changed his posture: rebuild the
            # strategy around who he is now.
            self.team_strategies[team.team_name] = self._generate_team_strategy(
                team, identity, sec)
    
    def _player_ask(self, player: Player, overall: Optional[float] = None,
                    league=None) -> int:
        """What the player demands: the same asking machinery the user
        faces. Base demand as % of cap scaled by the live cap, plus any
        market-setter premium, floored at $750k. Mirrors
        handle_contract_offer exactly, so the AI and the user negotiate
        against the same player."""
        try:
            from game_classes import to_100_scale as _t100
            _ovr100 = int(_t100(overall if overall is not None
                               else player.overall_rating()))
        except Exception:
            try:
                _ovr100 = int(overall if overall is not None
                             else player.overall_rating())
            except Exception:
                _ovr100 = 75
        _pos = getattr(player, "primary_position", "")
        _pos_name = _pos.value if hasattr(_pos, "value") else str(_pos)
        _age = int(getattr(player, "age", 27) or 27)
        # A player can only sign one ELC: a player currently on an ELC
        # asks second-contract money, not the ELC band.
        try:
            _on_elc = bool(getattr(getattr(player, "contract", None),
                                  "entry_level", False))
        except Exception:
            _on_elc = False
        _lg = league if league is not None else getattr(self, "_league_ref",
                                                       None)
        _season = int(getattr(_lg, "season_year", 0) or 0)
        _cap_sys = self._cap_system
        try:
            _cap = _cap_sys.current_cap if _cap_sys is not None \
                else DEFAULT_CAP
        except Exception:
            _cap = DEFAULT_CAP
        # Base demand follows the 2026 market-reset bands (superstar
        # 95+ $14-19M, premium 90+ $9-13.5M) -- the same logic the
        # league's contracts were generated on -- expressed as % of cap
        # so it scales, with any market-setter premium on top.
        from salary_cap_system import base_ask_dollars as _bad
        _base_pct = _bad(_ovr100, _age, _on_elc, _pos_name) / _cap
        try:
            if _cap_sys is not None:
                _ask = _cap_sys.demand_for(_base_pct, _ovr100, _pos_name,
                                           _age, _season)
            else:
                _ask = int(_base_pct * _cap)
        except Exception:
            _ask = int(_base_pct * _cap)
        return max(_ask, 750_000)

    def _offer_boldness(self, team: Team, strategy: TeamStrategy,
                        player: Player, ovr: float, ask: int,
                        available_budget: int) -> float:
        """How far above (or below) the player's ask this GM bids.

        The ask is what the player demands; the factor is the GM's
        competitive edge, in [0.90, 1.25]. The floor still signs -- the
        handshake accepts at 90% of ask -- so a disciplined GM banks the
        small discount and a bold GM pays real money for it. Boldness is
        never the default; it takes the right circumstances, all
        GM-side:
          - risk tolerance: the core dial. A gambler bids over; a
            cautious GM bids just under.
          - the missing piece: a contender whose #1 need is an impact
            player (85+) pays the overpay to complete the roster.
          - cap comfort: room after the deal invites boldness; a tight
            cap enforces discipline.
          - the seat: never bold under owner warning (the board leash);
            tenured winners stay conservative and trust their read; only
            a hot-seat GM wired to panic reaches out of desperation.
          - rebuilders never win bidding wars for veterans.
        """
        factor = 0.95 + 0.10 * strategy.risk_tolerance  # 0.95 - 1.05
        sec = self.gm_security.get(team.team_name)

        if strategy.priority == ManagementPriority.CONTEND:
            try:
                _needs = strategy.position_needs or []
                _missing = (bool(_needs)
                            and player.primary_position == _needs[0]
                            and ovr >= 85)
            except Exception:
                _missing = False
            if _missing:
                factor += 0.08

        try:
            _comfort = available_budget / max(1, strategy.budget_limit)
        except Exception:
            _comfort = 0.0
        if _comfort > 0.25:
            factor += 0.05
        elif _comfort < 0.08:
            factor -= 0.05

        if sec is not None:
            if sec.owner_warning:
                # Board leash: no bold offers on the way out.
                factor = min(factor, 1.0)
            elif sec.tenured_winner:
                # Conservative winner: doesn't bid against himself.
                factor -= 0.03
            elif sec.hot_seat:
                _ident = self.gm_identities.get(team.team_name)
                _pr = _ident.pressure_response \
                    if _ident is not None else 0.5
                if _pr >= 0.5:
                    # Desperate and wired to panic: reaches.
                    factor += 0.05

        if strategy.priority == ManagementPriority.REBUILD:
            factor = min(factor, 1.0)

        return max(0.90, min(1.25, factor))

    def _evaluate_free_agency(self, team: Team, strategy: TeamStrategy,
                             free_agents: List[Player], current_date: date) -> List[AIDecision]:
        """Evaluate free agent signings for a team"""
        decisions = []
        
        if not strategy.position_needs or not free_agents:
            return decisions
        
        # Calculate available budget
        current_salary = sum(getattr(p, 'salary', 750000) for p in team.roster)
        available_budget = strategy.budget_limit - current_salary
        # Forward book: money reserved for the franchise core's upcoming
        # raises is not UFA money. In a cap crunch there is no shopping.
        _fplan = self._ext_plans.get(team.team_name)
        if _fplan is not None:
            if _fplan.crunch:
                return decisions
            available_budget -= int(_fplan.reserved)
        
        if available_budget < 1_000_000:  # Need at least 1M available
            return decisions
        
        # Find suitable free agents. overall_rating() is computed ONCE per FA
        # here and threaded through: this runs per team per week, and the
        # old code recomputed it up to 4x per FA (sort key, priority x2,
        # offer details).
        suitable_fas = []
        for fa in free_agents:
            if fa.primary_position in strategy.position_needs:
                # Check age preference
                if strategy.prefer_youth and fa.age > strategy.max_roster_age:
                    continue
                if strategy.prefer_experience and fa.age < strategy.min_roster_age:
                    continue

                ovr = fa.overall_rating()
                # The offer: the player's ask, scaled by how bold this
                # GM is feeling -- his risk tolerance, the seat he's in,
                # whether this is the missing piece, and how comfortable
                # the cap is. No artificial ceiling on any UFA, Euro
                # imports included: the AI may bid anything from just
                # under the ask to a real overpay. Whether the player
                # ACCEPTS is decided realistically at execution time.
                ask = self._player_ask(fa, ovr)
                boldness = self._offer_boldness(team, strategy, fa, ovr,
                                               ask, available_budget)
                offer = int(ask * boldness)
                if offer <= available_budget:
                    suitable_fas.append((fa, offer, ovr, boldness))

        # Sort by priority (overall rating vs cost)
        suitable_fas.sort(key=lambda x: x[2] / (x[1] / 1_000_000), reverse=True)

        # Interest threshold moves with the GM's seat: a hot-seat GM chases
        # more targets -- but only as far as his personality bends under
        # pressure. A patient builder on the hot seat barely lowers his
        # standards; a GM under owner warning stops spending entirely (the board won't
        # approve splurges); a tenured winner waits for the right one.
        sec = self.gm_security.get(team.team_name)
        interest_threshold = 0.6
        if sec is not None:
            _ident = self.gm_identities.get(team.team_name)
            _pr = _ident.pressure_response if _ident is not None else 0.5
            if sec.owner_warning:
                interest_threshold = 0.75
            elif sec.hot_seat:
                interest_threshold = 0.6 - 0.15 * _pr
            elif sec.tenured_winner:
                interest_threshold = 0.72

        # Make offers to top candidates
        for fa, offer, ovr, boldness in suitable_fas[:3]:  # Top 3 candidates
            priority_score = self._calculate_fa_priority(fa, strategy, team, ovr)

            if priority_score > interest_threshold:
                decision = AIDecision(
                    team_name=team.team_name,
                    decision_type="free_agent_offer",
                    target_player=fa,
                    offer_details={
                        "salary": offer,
                        "term": self._determine_contract_length(fa, strategy),
                        "no_trade_clause": ovr > 85
                    },
                    priority_score=priority_score,
                    reasoning=(f"Addresses {fa.primary_position.value} need, "
                               f"fits strategy"
                               + (" -- bold bid for the missing piece"
                                  if boldness >= 1.10 else "")),
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
    
    # Potential-grade -> signing desirability (0..1). A user signs his
    # blue-chips early; the AI reads the same grades.
    _GRADE_SIGNING_DESIRE = {
        "A+": 0.95, "A": 0.90, "A-": 0.80,
        "B+": 0.62, "B": 0.55, "B-": 0.45,
        "C": 0.30, "D": 0.15, "F": 0.10,
    }

    def _evaluate_prospect_signings(self, team: Team, strategy: TeamStrategy,
                                    identity: GMIdentity, sec: GMJobSecurity,
                                    current_date: date) -> List[AIDecision]:
        """Decide which drafted rookies deserve an ELC right now.

        A prospect gets signed when he deserves it -- top grades, NHL-ready
        production, fills a real roster hole -- or when he needs it: his
        rights expire within a season and the club would lose the asset for
        nothing. Signing urgency comes from the GM's identity: patient
        developers lock up talent early, hot-seat GMs rush help, tenured
        winners can afford to wait.
        """
        decisions = []
        league = getattr(self, "_league_ref", None)
        if league is None:
            return decisions
        prospects = getattr(team, "prospects", None) or []
        if not prospects:
            return decisions
        try:
            season_year = int(getattr(league, "season_year", current_date.year))
        except (TypeError, ValueError):
            season_year = current_date.year

        urgency = signing_urgency(identity, sec)
        # Urgent GMs sign at 0.40, patient-at-rest GMs need 0.75.
        threshold = 0.75 - 0.35 * urgency

        for p in prospects:
            try:
                if getattr(p, "contract", None) is not None:
                    continue  # already signed
                if getattr(p, "rights_team", "") != team.team_name:
                    continue  # not our rights
                if getattr(p, "retired", False):
                    continue

                grade = str(getattr(p, "potential_grade", "C") or "C").strip()
                deserve = self._GRADE_SIGNING_DESIRE.get(grade, 0.30)
                try:
                    ovr = float(p.overall_rating())
                except Exception:
                    ovr = 60.0
                age = int(getattr(p, "age", 20) or 20)
                # NHL-ready now: a user burns the ELC year for real help.
                if ovr >= 75 and age >= 20:
                    deserve = min(1.0, deserve + 0.20)
                elif ovr >= 70 and age >= 20:
                    deserve = min(1.0, deserve + 0.10)
                # Fills a positional hole on the big club.
                if p.primary_position in strategy.position_needs and ovr >= 68:
                    deserve = min(1.0, deserve + 0.15)

                # Rights clock: losing a prospect for nothing is malpractice.
                expiry = getattr(p, "rights_expiry_year", 0) or 0
                years_left = (expiry - season_year) if expiry else 99
                need = 1.0 if years_left <= 1 else (0.45 if years_left == 2 else 0.0)

                score = max(deserve, need)
                if score < threshold:
                    continue

                reason = ("Rights expire soon -- sign or lose the asset"
                          if need >= score and need >= 0.9
                          else f"Top prospect ({grade}) ready to turn pro")
                decisions.append(AIDecision(
                    team_name=team.team_name,
                    decision_type="sign_prospect",
                    target_player=p,
                    offer_details={"elc": True, "score": round(score, 2),
                                   "rights_years_left": years_left},
                    priority_score=round(score, 2),
                    reasoning=f"{identity.gm_name}: {reason}",
                    timestamp=current_date,
                ))
                if len(decisions) >= 2:  # at most two signings per week
                    break
            except Exception:
                continue

        return decisions

    def _execute_free_agent_signing(self, team: Team, decision: "AIDecision",
                                      league) -> bool:
        """Execute one AI free-agent signing end-to-end.

        Same rulebook as the user/MP paths: draft lock, 23-man roster
        limit, league-minimum salary, a live budget re-check (not the
        evaluation-time number), and the 6-year external max from the new
        CBA. The handshake is realistic: the player weighs the offer
        against the SAME asking machinery the user faces (cap-relative
        base demand plus any market-setter premium, floored at $750k).
        At 90%+ of his ask he signs; at 70-90% the AI meets the ask when
        the budget allows, otherwise the player walks; below 70% he walks
        outright. The AI may offer anything from the minimum to its full
        cap room -- selectivity lives in WHICH players get offers
        (priority threshold, needs, budget), not in an artificial
        ceiling. The rivalry transfer hooks fire so the ledger can't go
        stale: his personal beefs follow him to the new room.
        Returns True when a signing completed.
        """
        p = getattr(decision, "target_player", None)
        details = getattr(decision, "offer_details", None) or {}
        if p is None:
            return False
        try:
            # Still on the market?
            fa_pool = getattr(league, "free_agents", None)
            if not isinstance(fa_pool, list) or p not in fa_pool:
                return False
            # Draft lock: shared rule, no sidestepping the draft.
            try:
                from draft_generator import player_locked_by_draft as _locked
                if _locked(p):
                    return False
            except Exception:
                pass
            # A real hole: roster room and the position still a need.
            roster = getattr(team, "roster", None) or []
            if len(roster) >= 23:
                return False
            strategy = self.team_strategies.get(team.team_name)
            if strategy is None or \
                    getattr(p, "primary_position", None) not in \
                    (strategy.position_needs or []):
                return False
            # Terms: 6-year external max (new CBA). The offer itself may be
            # anything from the minimum to the full cap room.
            offered = int(details.get("salary", 0) or 0)
            years = max(1, min(6, int(details.get("term", 1) or 1)))
            # The handshake: what would he take? The SAME asking
            # machinery the user faces, so the AI and the user negotiate
            # against the same player.
            _ask = self._player_ask(p, league=league)
            # The user's rulebook, without a counter loop: 90%+ of ask
            # signs on the spot; 70-90% is the counter zone, where the AI
            # meets the ask when the budget allows and walks otherwise;
            # below 70% the player is insulted and walks outright.
            if offered >= 0.9 * _ask:
                salary = offered
            elif offered >= 0.7 * _ask:
                salary = _ask
            else:
                return False
            try:
                from salary_cap_system import league_minimum_salary as _min_fn
                _floor = _min_fn(getattr(league, "season_year", None))
            except Exception:
                _floor = 850_000
            if salary < _floor:
                return False
            # Live budget re-check against the strategy's spending limit.
            try:
                current = sum(int(getattr(x, "salary", 750_000) or 750_000)
                              for x in roster)
            except Exception:
                current = 0
            if salary > (strategy.budget_limit - current):
                return False
            # The handshake: offer is estimated market value -- accepted.
            p.salary = salary
            p.contract_years = years
            # A new SPC starts with no retained salary, same as every path.
            try:
                import trade_engine as _te_clr
                _te_clr.clear_retention_state(p)
            except Exception:
                pass
            _contract = getattr(p, "contract", None)
            if _contract is not None:
                _contract.salary = salary
                _contract.years_remaining = years
                if details.get("no_trade_clause"):
                    try:
                        import trade_engine as _te2
                        if _te2.clause_eligible(p):
                            _te2.apply_clause_to_contract(
                                _contract, "ntc", 10, player=p)
                    except Exception:
                        pass
            fa_pool.remove(p)
            team.add_player(p, "roster")
            # Rivalry lifecycle: a signing is a transfer.
            try:
                from reputation_system import on_player_transfer as _opt
                _rivs = getattr(league, "rivalries", None)
                if isinstance(_rivs, list):
                    _opt(_rivs, p, from_team=None, to_team=team)
            except Exception:
                pass
            # Dressing room: AI rooms react to WHO arrives, same as the
            # user's room -- even playing field.
            try:
                import dressing_room as _dr_arr
                _dr_arr.cascade_on_arrival(team, p, how="signing")
            except Exception:
                pass
            # Market feedback: Caleb's market engine learns from EVERY
            # signing, not just the user's. register_signing keeps only
            # true market-setters (star + top-5 AAV) as comps; those comps
            # feed market_premium, which is exactly what the handshake's
            # _player_ask prices in. So a bold AI overpay for a star
            # raises the next star's ask -- offers change the league.
            # The human fallout lands on AI GMs exactly like the user:
            # overpay verdict, fan beef, GM rep, GM-GM heat.
            _set_market = False
            try:
                _cap_sys2 = getattr(league, "salary_cap_system", None)
                if _cap_sys2 is not None:
                    _p2 = getattr(p, "primary_position", "")
                    _pn2 = _p2.value if hasattr(_p2, "value") else str(_p2)
                    try:
                        from game_classes import to_100_scale as _t100b
                        _ovr100b = int(_t100b(p.overall_rating()))
                    except Exception:
                        _ovr100b = 75
                    _set_market = bool(_cap_sys2.register_signing(
                        getattr(p, "full_name", "Unknown"), salary,
                        _ovr100b, _pn2,
                        int(getattr(p, "age", 27) or 27),
                        int(getattr(league, "season_year", 0) or 0)))
            except Exception:
                pass
            try:
                from reputation_system import evaluate_contract_decision \
                    as _ecd
                _cd = _ecd(p, salary, _ask, team=team, league=league,
                           market_setter=bool(_set_market))
            except Exception:
                _cd = {}
            # Stories queue on the manager; the app flushes them into the
            # news feed with today's date (the manager holds no app ref).
            try:
                _pname = getattr(p, "full_name", "Unknown")
                _stories = [
                    f"The {team.team_name} have signed {_pname} to a "
                    f"{years}-year contract."]
                if _set_market:
                    _stories.append(
                        f"{_pname}'s ${salary:,} deal sets the market -- "
                        f"comparable stars will demand more.")
                if isinstance(_cd, dict) and _cd.get("story"):
                    _stories.append(_cd["story"])
                _pend = getattr(self, "_pending_news", None)
                if not isinstance(_pend, list):
                    _pend = self._pending_news = []
                _pend.extend(_stories)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _execute_contract_extension(self, team: Team, decision: "AIDecision",
                                      league) -> bool:
        """Execute one AI contract extension end-to-end.

        The same rulebook as the user's extension path: league-minimum
        salary, 20%-of-cap max, 7-year re-sign max (new CBA), and the cap
        check where the extension REPLACES the player's existing hit
        rather than stacking on top of it. The player decides through
        the same contract_appeal machinery that governs offer sheets and
        UFA talks -- loyalty, happiness, cup contention, role, and money
        all weigh in, so a disgruntled star can still walk to free
        agency. Star market-setters move the market via register_signing,
        and the human fallout (overpay verdict, fan reaction) lands on
        the AI GM exactly like the user. Returns True when the player
        signs.
        """
        p = getattr(decision, "target_player", None)
        details = getattr(decision, "offer_details", None) or {}
        if p is None:
            return False
        try:
            # Still here, still on an expiring deal?
            roster = getattr(team, "roster", None) or []
            if p not in roster:
                return False
            _contract = getattr(p, "contract", None)
            if _contract is None:
                return False
            # Same rulebook as the user and the evaluator above: the
            # extension window in transaction_windows, not a local copy.
            try:
                import transaction_windows as _twx
                _xok, _xwhy = _twx.check_window(
                    "extension", None, ctx={"player": p})
                if not _xok:
                    return False
            except Exception:
                pass
            try:
                from player_decision import wants_out as _wo
                if _wo(p):
                    return False
            except Exception:
                pass
            # Terms: clamp to the user's rulebook (7-year re-sign max,
            # league minimum, 20% of cap). The evaluation may propose 8
            # for young stars (old-CBA habit); the new CBA caps it at 7.
            try:
                from salary_cap_system import league_minimum_salary as _min_fn
                _floor = int(_min_fn(getattr(league, "season_year", None)))
            except Exception:
                _floor = 850_000
            try:
                _cap_sys = getattr(league, "salary_cap_system", None)
                _live_cap = int(_cap_sys.current_cap) if _cap_sys else 104_000_000
            except Exception:
                _live_cap = 104_000_000
            _max_sal = int(0.20 * _live_cap)
            offered = int(details.get("salary", 0) or 0)
            years = max(1, min(7, int(details.get("term", 1) or 1)))
            if offered < _floor or offered > _max_sal:
                return False
            # Cap check, mirroring the user's extension validation: the
            # new money replaces the player's existing hit.
            try:
                from salary_cap_system import total_cap_charge as _tcc
                _charge = int(_tcc(team))
                _cur = int(getattr(_contract, "salary", 0) or 0)
                if _charge - _cur + offered > _live_cap:
                    return False
            except Exception:
                pass
            # The handshake: the SAME appeal machinery as offer sheets /
            # UFA talks, with the stay-home bonus (current_team is team).
            # A soft yes isn't enough -- mirrors the offer-sheet bar.
            # Insult guard (same zones as the FA handshake): below 70% of
            # his ask the player walks outright -- no loyalty discount
            # covers an 8%-of-market offer.
            try:
                _ask0 = self._player_ask(p, league=league)
            except Exception:
                _ask0 = 0
            if _ask0 and offered < 0.7 * _ask0:
                try:
                    _pend = getattr(self, "_pending_news", None)
                    if not isinstance(_pend, list):
                        _pend = self._pending_news = []
                    _pend.append(
                        f"{getattr(p, 'full_name', 'A player')} turned down "
                        f"the {team.team_name}' extension offer "
                        f"(${offered:,} x {years}) -- he'll test the market.")
                except Exception:
                    pass
                return False
            try:
                from player_decision import contract_appeal as _appeal
                _score, _reasons = _appeal(
                    p, team, offered, years,
                    current_team=team, league=league)
            except Exception:
                return False
            # Deterministic bar (the offer-sheet 0.52, minus the jitter):
            # weekly processing re-proposes identical terms (the ask and
            # the boldness are both deterministic), so a jittered roll
            # would re-litigate the same rejected offer every week. A
            # rejection stands until the terms change.
            if _score < 0.52:
                try:
                    _pend = getattr(self, "_pending_news", None)
                    if not isinstance(_pend, list):
                        _pend = self._pending_news = []
                    _pend.append(
                        f"{getattr(p, 'full_name', 'A player')} turned down "
                        f"the {team.team_name}' extension offer "
                        f"(${offered:,} x {years}) -- he'll test the market.")
                except Exception:
                    pass
                return False
            # Signed. Mutate in place like the user's extension path.
            _contract.salary = offered
            _contract.years_remaining = years
            # An ELC extension is a second contract, not an ELC: the
            # slide machinery must not touch it again.
            try:
                _contract.entry_level = False
                p.elc_slides_used = 0
                p.elc_seasons_completed = 0
            except Exception:
                pass
            # Trade protection for established veterans on long deals --
            # the user can offer clauses in extensions; the AI does too.
            try:
                import trade_engine as _te
                if years >= 4 and _te.clause_eligible(p):
                    _te.apply_clause_to_contract(
                        _contract, "ntc", 10, player=p)
            except Exception:
                pass
            # Market feedback + human fallout, same as every signing path.
            _ask = None
            try:
                _ask = self._player_ask(p, league=league)
            except Exception:
                pass
            _set_market = False
            try:
                _cap_sys2 = getattr(league, "salary_cap_system", None)
                if _cap_sys2 is not None:
                    _p2 = getattr(p, "primary_position", "")
                    _pn2 = _p2.value if hasattr(_p2, "value") else str(_p2)
                    try:
                        from game_classes import to_100_scale as _t100c
                        _ovr100c = int(_t100c(p.overall_rating()))
                    except Exception:
                        _ovr100c = 75
                    _set_market = bool(_cap_sys2.register_signing(
                        getattr(p, "full_name", "Unknown"), offered,
                        _ovr100c, _pn2,
                        int(getattr(p, "age", 27) or 27),
                        int(getattr(league, "season_year", 0) or 0)))
            except Exception:
                pass
            try:
                from reputation_system import evaluate_contract_decision \
                    as _ecd
                _cd = _ecd(p, offered, _ask if _ask else offered,
                           team=team, league=league,
                           market_setter=bool(_set_market))
            except Exception:
                _cd = {}
            try:
                _pname = getattr(p, "full_name", "Unknown")
                _stories = [
                    f"The {team.team_name} have signed {_pname} to a "
                    f"{years}-year, ${offered:,}/yr extension."]
                if _set_market:
                    _stories.append(
                        f"{_pname}'s ${offered:,}/yr extension sets the "
                        f"market -- comparable stars will demand more.")
                if isinstance(_cd, dict) and _cd.get("story"):
                    _stories.append(_cd["story"])
                _pend = getattr(self, "_pending_news", None)
                if not isinstance(_pend, list):
                    _pend = self._pending_news = []
                _pend.extend(_stories)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _execute_decisions(self, team: Team, decisions: List[AIDecision]):
        """Execute the decisions this manager owns end-to-end.

        Signings go through the league's real signing path (same ELC rules
        the user gets). Promotions are gated: unsigned prospects cannot be
        promoted, and signed prospects who are not AHL-eligible stay on the
        junior track instead of being parked in the minors.
        """
        league = getattr(self, "_league_ref", None)
        if league is None:
            return
        _fa_signed = False  # at most one signing per team per weekly tick:
        # the evaluation proposes up to 3 targets, but executing all of
        # them would drain the pool in a week. First valid handshake wins.
        for d in decisions:
            try:
                p = d.target_player
                if p is None:
                    continue
                if d.decision_type == "free_agent_offer":
                    if not _fa_signed and self._execute_free_agent_signing(
                            team, d, league):
                        _fa_signed = True
                    continue
                if d.decision_type == "contract_extension":
                    # Real executor, not a proposal: same rulebook as the
                    # user's extension path (cap, term, player handshake).
                    self._execute_contract_extension(team, d, league)
                    continue
                if d.decision_type == "sign_prospect":
                    if getattr(p, "contract", None) is not None:
                        continue
                    if hasattr(league, "sign_drafted_prospect"):
                        league.sign_drafted_prospect(team, p)
                elif d.decision_type == "promote_prospect":
                    prospects = getattr(team, "prospects", None)
                    ahl = getattr(team, "ahl_roster", None)
                    if prospects is None or ahl is None or p not in prospects:
                        continue
                    # Unsigned prospects have no SPC: sign first, promote later.
                    if getattr(p, "contract", None) is None:
                        continue
                    # Junior-track prospects stay in the prospects pool (their
                    # junior club), never the AHL.
                    try:
                        from game_classes import prospect_ahl_eligible
                        if not prospect_ahl_eligible(p):
                            continue
                    except Exception:
                        pass
                    prospects.remove(p)
                    ahl.append(p)
            except Exception:
                continue

    def _build_extension_plan(self, team: Team, identity, strategy,
                              current_date: date):
        """One club's forward book for this pass (ai_extension_planning).

        Who the GM considers franchise pieces (stars AND the young future
        core), what their next deals project to, and how much of today's
        money is already spoken for.
        """
        import ai_extension_planning as _aep
        try:
            from salary_cap_system import total_cap_charge as _tcc
        except Exception:
            _tcc = None
        try:
            from salary_cap_system import league_minimum_salary as _lms
            _lmin = int(_lms())
        except Exception:
            _lmin = 775_000
        _cap_sys = getattr(self, "_cap_system", None)
        _ceiling = int(_cap_sys.current_cap) if _cap_sys is not None \
            else 104_000_000
        try:
            _charge = int(_tcc(team)) if _tcc is not None else 0
        except Exception:
            _charge = 0
        if _charge <= 0:
            _charge = sum(int(getattr(getattr(p, "contract", None),
                                      "salary", 0) or 0)
                          for p in (getattr(team, "roster", None) or []))
        _lg = getattr(self, "_league_ref", None)
        _ask = lambda p: self._player_ask(p, league=_lg)
        return _aep.plan(team, identity=identity, strategy=strategy,
                         ask_fn=_ask, cap_ceiling=_ceiling,
                         current_charge=_charge, current_date=current_date,
                         league_min=_lmin)

    def _evaluate_contract_extensions(self, team: Team, strategy: TeamStrategy,
                                    current_date: date) -> List[AIDecision]:
        """Evaluate contract extension opportunities.

        Candidates are players whose contracts genuinely expire after this
        season (years_remaining == 1) -- not a random sample. Players who
        want out skip extensions entirely; they use the holdout path.
        """
        decisions = []

        # Find players with expiring contracts
        try:
            from player_decision import wants_out as _wants_out
        except Exception:
            _wants_out = None
        # Eligibility is the SHARED rulebook -- the exact function gating
        # the user's extension path (transaction_windows.check_window).
        # Final year of the deal, including the June exclusive re-sign
        # window after age_one_year decrements years_remaining to 0.
        # No parity gap in either direction: the AI gets exactly the
        # window the user gets.
        try:
            import transaction_windows as _tw
            _tw_ok = lambda p: _tw.check_window(
                "extension", current_date, ctx={"player": p})[0]
        except Exception:
            _tw_ok = lambda p: True
        expiring_players = []
        for player in team.roster:
            try:
                _c = getattr(player, 'contract', None)
                if _c is None:
                    continue
                if not _tw_ok(player):
                    continue
                if _wants_out is not None and _wants_out(player):
                    continue
                expiring_players.append(player)
            except Exception:
                continue
        
        # The forward book orders the table: franchise pieces negotiate
        # first, and non-pieces spend only from the discretionary remainder.
        # When the plan says next summer's $15M man owns the money, the
        # questionable piece waits.
        _plan0 = self._ext_plans.get(team.team_name)
        _plan_remaining = int(_plan0.discretionary) if _plan0 is not None \
            else 10 ** 12
        if _plan0 is not None:
            _order = {id(q["player"]): i for i, q in enumerate(_plan0.queue)}
            expiring_players.sort(key=lambda p: _order.get(id(p), 10 ** 6))

        for player in expiring_players:
            # Decide whether to extend based on strategy. A player coming
            # off his ELC is always an extension candidate -- he's your
            # own drafted kid, not a roster-shape decision; the strategy
            # question is the terms, not whether to make an offer.
            # (Non-tendering him means losing the asset for nothing.)
            try:
                _on_elc = bool(getattr(
                    getattr(player, "contract", None), "entry_level",
                    False))
            except Exception:
                _on_elc = False
            should_extend = (_on_elc
                             or self._should_extend_player(player, strategy))
            
            if should_extend:
                # Young stars get top extension priority: sign them a year
                # early at today's market rather than risking next year's
                # ask after another cap jump (the Carlsson lesson).
                try:
                    from game_classes import to_100_scale
                    _ovr100 = int(to_100_scale(player.overall_rating()))
                except Exception:
                    _ovr100 = 75
                _young_star = player.age <= 24 and _ovr100 >= 90
                # A GM on the hot seat pushes extensions through faster --
                # losing a star for nothing is a firing offense -- but only
                # as far as his personality bends. A builder who trusts his
                # vision doesn't panic; a warned GM can't get big money
                # approved anyway.
                _sec = self.gm_security.get(team.team_name)
                _urgency = 0.95 if _young_star else 0.8
                if _sec is not None and _sec.hot_seat and not _sec.owner_warning:
                    _ident2 = self.gm_identities.get(team.team_name)
                    _pr2 = _ident2.pressure_response if _ident2 is not None else 0.5
                    _urgency = min(1.0, _urgency + 0.1 * _pr2)
                # The offer anchors to the player's ASK (the same number
                # the user negotiates against), scaled by this GM's
                # boldness -- exactly like the FA path. Anchoring to the
                # internal estimate instead would systematically lowball:
                # the handshake zones are measured against the ask.
                try:
                    _ask_e = self._player_ask(player, league=getattr(
                        self, "_league_ref", None))
                except Exception:
                    _ask_e = self._estimate_player_salary(player)
                try:
                    from salary_cap_system import total_cap_charge as _tcc_e
                    _cap_sys_e = getattr(self, "_cap_system", None)
                    _cap_e = int(_cap_sys_e.current_cap) \
                        if _cap_sys_e else 104_000_000
                    _room_e = _cap_e - (int(_tcc_e(team)) - int(
                        getattr(getattr(player, "contract", None),
                                "salary", 0) or 0))
                except Exception:
                    _room_e = 0
                try:
                    _bold_e = self._offer_boldness(
                        team, strategy, player, player.overall_rating(),
                        _ask_e, max(0, _room_e))
                except Exception:
                    _bold_e = 0.95
                _offer_e = int(_ask_e * _bold_e)
                if _offer_e > max(0, _room_e):
                    # Can't afford the ask: skip rather than insult him.
                    continue
                _is_piece_e = False
                if _plan0 is not None:
                    _is_piece_e = any(q["player"] is player and q["is_piece"]
                                      for q in _plan0.queue)
                if not _is_piece_e and _offer_e > max(0, _plan_remaining):
                    # The forward book has this money earmarked for the
                    # core's upcoming raises -- not for depth today.
                    continue
                if not _is_piece_e:
                    _plan_remaining -= _offer_e
                decision = AIDecision(
                    team_name=team.team_name,
                    decision_type="contract_extension",
                    target_player=player,
                    offer_details={
                        "salary": _offer_e,
                        "term": self._determine_contract_length(player, strategy)
                    },
                    priority_score=_urgency,
                    reasoning=("Lock up young star early before the "
                                "market moves" if _young_star
                                else "Key player fitting strategy"),
                    timestamp=current_date
                )
                decisions.append(decision)
        
        return decisions
    
    def _estimate_player_salary(self, player: Player,
                                overall: Optional[float] = None) -> int:
        """Estimate fair market salary for a player.

        Mirrors the generation gates (player_generator CONTRACT_VALUES)
        so AI offers match the market the league was built on -- the
        2026 summer reset (Makar $20.4M, Celebrini $18.8M, Carlsson $18M
        at 21, Kaprizov $17M). Young stars are valued at star money, not
        bridged: waiting only raises their ask as the cap climbs, so the
        market pays them upfront. Demands flow through demand_for, so
        market-setter premiums still apply on top.
        """
        cap_sys = self._cap_system
        cap = cap_sys.current_cap if cap_sys else DEFAULT_CAP

        # overall_rating() is ~30 lines of arithmetic: callers in hot loops
        # (e.g. _evaluate_free_agency over 32 teams x FAs) pass it in.
        ovr = overall if overall is not None else player.overall_rating()
        # overall_rating() is native 1-100; to_100_scale is a passthrough.
        try:
            from game_classes import to_100_scale
            ovr100 = int(to_100_scale(ovr))
        except Exception:
            ovr100 = int(ovr)
        age = player.age

        # Category mirrors PlayerGenerator.determine_contract_info, except
        # stars are priced as stars at any age -- a 21-year-old franchise
        # player coming off his ELC asks for $16M+, not another ELC.
        # A player can only sign one ELC: if his current deal is
        # entry-level, the ELC band below does not apply -- the extension
        # is a second contract priced on the regular youth curve.
        try:
            _on_elc = bool(getattr(getattr(player, "contract", None),
                                   "entry_level", False))
        except Exception:
            _on_elc = False
        if ovr100 >= 95:
            lo, hi, f = 14_000_000, 19_000_000, (ovr100 - 94) / 6
        elif ovr100 >= 90:
            lo, hi, f = 9_000_000, 13_500_000, (ovr100 - 89) / 6
        elif age <= 22 and not _on_elc:
            # New-CBA ELC band: floor = signing-season league minimum,
            # ceiling = max flat-salary equivalent (AAV) for the deal
            # length (3 years at <=21, 2 years at 22).
            try:
                from salary_cap_system import league_minimum_salary as _lms3
                from salary_cap_system import elc_max_salary as _elc3
                lo, hi = int(_lms3()), int(_elc3(3 if age <= 21 else 2))
            except Exception:
                lo, hi = 775_000, 975_000
            f = (ovr100 - 62) / 28
        elif age <= 25 and ovr100 < 80:
            lo, hi, f = 1_200_000, 5_000_000, (ovr100 - 62) / 28
        elif age >= 33 and ovr100 < 84:
            try:
                from salary_cap_system import league_minimum_salary as _lms4
                _vlo = int(_lms4())
            except Exception:
                _vlo = 775_000
            lo, hi, f = _vlo, 3_750_000, (ovr100 - 62) / 28
        else:
            lo, hi, f = 1_000_000, 6_500_000, (ovr100 - 62) / 28
        f = max(0.0, min(1.0, f))
        base_salary = lo + (hi - lo) * f

        # Position adjustments (kept small: generation is position-blind)
        pos = player.primary_position
        if pos == PlayerPosition.GOALIE:
            base_salary *= 1.1
        elif pos == PlayerPosition.CENTER:
            base_salary *= 1.05

        # Convert to cap % so demands scale with the cap, then apply any
        # market-setter premium through the single choke point.
        base_cap_pct = base_salary / cap
        pos_name = pos.value if hasattr(pos, "value") else str(pos)
        if cap_sys:
            league = getattr(self, "_league_ref", None)
            season = getattr(league, "season_year", 0) if league else 0
            salary = cap_sys.demand_for(base_cap_pct, ovr100, pos_name,
                                        age, season)
        else:
            salary = int(base_salary)

        # Clamp: league min to 20% of cap (NHL max)
        return max(min(int(salary), int(cap * 0.20)), 750_000)
    
    def _determine_contract_length(self, player: Player, strategy: TeamStrategy) -> int:
        """Determine appropriate contract length.

        Young stars get max term up front -- the 2026 market pays for
        prime years early (Cooley 8x$80M at 21, Carlsson offered 8x$84M
        at 21, Gauthier 6x$13.5M) because waiting a year only raises the
        ask as the cap climbs.
        """
        try:
            from game_classes import to_100_scale
            ovr100 = int(to_100_scale(player.overall_rating()))
        except Exception:
            ovr100 = 75
        if player.age <= 24 and ovr100 >= 90:
            return random.randint(6, 8)  # Lock up the young star now
        if player.age < 26:
            return random.randint(2, 5)  # Bridge or long-term for youth
        elif player.age < 30:
            return random.randint(3, 7)  # Prime years
        else:
            return random.randint(1, 3)  # Short term for veterans
    
    def _calculate_fa_priority(self, player: Player, strategy: TeamStrategy,
                               team: Team,
                               overall: Optional[float] = None) -> float:
        """Calculate how much a team wants a free agent"""
        priority = 0.0
        ovr = overall if overall is not None else player.overall_rating()

        # Position need bonus
        if player.primary_position in strategy.position_needs:
            priority += 0.4

        # Overall rating bonus
        priority += min(ovr / 170, 0.3)  # 51 OVR -> full 0.3

        # Age preference
        if strategy.prefer_youth and player.age < 26:
            priority += 0.2
        elif strategy.prefer_experience and player.age > 28:
            priority += 0.2

        # Strategic fit
        if strategy.priority == ManagementPriority.CONTEND and ovr > 85:
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
