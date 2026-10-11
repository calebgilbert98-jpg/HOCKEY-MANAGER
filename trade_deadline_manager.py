# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""
Trade Deadline Manager - Core Backend Logic for Trade Deadline Day
Handles deadline detection, trade validation, and deadline-specific trading rules
"""

import random
from datetime import datetime, date, time, timedelta
from typing import (Dict, List, Tuple, Any)


# The NHL CBA (Article 13.12(j)) sets the deadline at 3pm ET on the 40th
# day immediately preceding the final day of the regular season. The
# game derives it from the generated schedule: last regular-season game
# date minus 40 days. At that point clubs are ~75% through their games,
# which is why it also reads as a "completion %" rule.
TRADE_DEADLINE_LEAD_DAYS = 40


def trade_deadline_date(league=None, deadline_year=None):
    """Return this season's trade deadline as a datetime.date.

    Derived from the league schedule: 40 days before the final day of
    the regular season (NHL CBA logic). Preseason exhibitions, playoff
    games, and special-event entries never move it. Falls back to
    March 8 of the deadline year when the schedule can't answer (no
    league, QA stubs, saves from before the schedule existed).
    """
    try:
        sched = getattr(league, "schedule", None) or []
        last = None
        for e in sched:
            if not isinstance(e, dict):
                continue
            if e.get("league") != "NHL":
                continue
            if e.get("preseason") or e.get("playoff"):
                continue
            d = e.get("date")
            if d is None:
                continue
            try:
                dd = d.date() if isinstance(d, datetime) else d
            except Exception:
                continue
            if last is None or dd > last:
                last = dd
        if last is not None:
            return last - timedelta(days=TRADE_DEADLINE_LEAD_DAYS)
    except Exception:
        pass
    try:
        syr = int(getattr(league, "season_year", 0) or 0)
    except Exception:
        syr = 0
    dy = deadline_year or (syr + 1 if syr else datetime.now().year)
    try:
        return date(dy, 3, 8)
    except Exception:
        return date(datetime.now().year, 3, 8)


class TradeDeadlineManager:
    """Manages all trade deadline day logic and constraints"""
    
    # NHL Trade Deadline Constants. The date itself is DERIVED from the
    # schedule (see trade_deadline_date); these month/day constants are
    # only the fallback when no schedule can answer.
    DEADLINE_MONTH = 3
    DEADLINE_DAY = 8
    DEADLINE_HOUR = 15  # 3 PM ET
    DEADLINE_MINUTE = 0

    # Deadline-day game clock: the day runs 9:00 AM -> 3:00 PM ET in
    # 30-minute increments (the "rush"). Game-time, not wall-clock.
    CLOCK_START_MIN = 9 * 60
    CLOCK_END_MIN = 15 * 60
    CLOCK_STEP_MIN = 30

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

        # Game-clock state (persisted on game_manager.deadline_clock;
        # mirrors it here for convenience). Keys: date (iso), minutes,
        # expired.
        self._clock = {'date': None, 'minutes': self.CLOCK_START_MIN,
                       'expired': False}
        
        # Breaking news tracking
        self.breaking_news = []
        self.last_breaking_news_check = datetime.now()
        # Dedup set for breaking-news strings already emitted this
        # process (kept bounded). Stored as a set so repeated deadline-
        # day polls don't re-announce the same fact.
        self._news_shown = set()
        
        # Initialize team market activity
        self._initialize_team_strategies()

    def reset_for_new_season(self):
        """Clear per-season deadline state at the offseason rollover.

        Without this the singleton keeps last season's trade activity log
        (stale "hot"/"warm" intel) and last season's buyer/seller
        strategies into the new year.
        """
        self.trade_activity_log = []
        self.breaking_news = []
        self.deadline_passed = False
        self._news_shown = set()
        self.deadline_stats = {
            'total_trades': 0,
            'players_moved': 0,
            'biggest_deal_value': 0,
            'most_active_team': None,
            'deadline_minute_trades': 0
        }
        self._initialize_team_strategies()
        self._clock = {'date': None, 'minutes': self.CLOCK_START_MIN,
                       'expired': False}
        
    def deadline_date(self):
        """This season's trade deadline as a date.

        Derived from the league schedule (40 days before the final day
        of the regular season, per the CBA); falls back to March 8 when
        the schedule can't answer. Never raises.
        """
        try:
            league = getattr(self.game_manager, "league", None)
        except Exception:
            league = None
        try:
            return trade_deadline_date(league)
        except Exception:
            return date(self.DEADLINE_MONTH, self.DEADLINE_DAY)

    def is_trade_deadline_day(self, current_date=None) -> bool:
        """Check if the current date is trade deadline day (derived)."""
        check_date = current_date or datetime.now()
        try:
            dd = self.deadline_date()
            cd = (check_date.date() if isinstance(check_date, datetime)
                  else check_date)
            return cd == dd
        except Exception:
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
    
    def is_deadline_day(self, game_date) -> bool:
        """Game-date check: is this game date trade deadline day?"""
        try:
            dd = self.deadline_date()
            gd = (game_date.date() if isinstance(game_date, datetime)
                  else game_date)
            return gd == dd
        except Exception:
            try:
                return (game_date.month == self.DEADLINE_MONTH and
                        game_date.day == self.DEADLINE_DAY)
            except Exception:
                return False

    # ------------------------------------------------------------------
    # Deadline-day game clock (30-minute increments, 9 AM -> 3 PM ET)
    # ------------------------------------------------------------------
    def _clock_store(self) -> dict:
        """Persisted clock dict; lives on game_manager so saves keep it."""
        gm = self.game_manager
        if gm is not None:
            store = getattr(gm, 'deadline_clock', None)
            if isinstance(store, dict) and store.get('date'):
                self._clock = store
                return store
        return self._clock

    def _save_clock(self) -> None:
        try:
            if self.game_manager is not None:
                self.game_manager.deadline_clock = dict(self._clock)
        except Exception:
            pass

    def start_clock(self, game_date) -> None:
        """Begin the deadline-day clock at 9:00 AM ET."""
        iso = game_date.isoformat() if hasattr(game_date, 'isoformat') else str(game_date)
        if self._clock.get('date') == iso and not self._clock.get('expired'):
            return  # already running today
        self._clock = {'date': iso, 'minutes': self.CLOCK_START_MIN,
                       'expired': False}
        self.deadline_passed = False
        self._save_clock()

    def clock_active(self, game_date=None) -> bool:
        c = self._clock_store()
        if not c.get('date') or c.get('expired'):
            return False
        if game_date is not None:
            iso = game_date.isoformat() if hasattr(game_date, 'isoformat') else str(game_date)
            if c['date'] != iso:
                return False
        return True

    def clock_minutes(self) -> int:
        return int(self._clock_store().get('minutes', self.CLOCK_START_MIN))

    def clock_display(self) -> str:
        """'11:30 AM ET' for the current clock position."""
        m = self.clock_minutes()
        h, mm = divmod(m, 60)
        suffix = 'AM' if h < 12 else 'PM'
        h12 = h % 12 or 12
        return f"{h12}:{mm:02d} {suffix} ET"

    def clock_progress(self) -> float:
        """0.0 at 9 AM -> 1.0 at 3 PM. Drives deadline urgency."""
        span = self.CLOCK_END_MIN - self.CLOCK_START_MIN
        return max(0.0, min(1.0,
                            (self.clock_minutes() - self.CLOCK_START_MIN) / span))

    def time_until_close(self) -> timedelta:
        return timedelta(minutes=max(0, self.CLOCK_END_MIN - self.clock_minutes()))

    def advance_clock(self, minutes: int = None) -> dict:
        """Move the clock forward. Returns {'minutes','display','expired'}."""
        step = minutes if minutes else self.CLOCK_STEP_MIN
        c = self._clock_store()
        c['minutes'] = int(c.get('minutes', self.CLOCK_START_MIN)) + step
        expired = c['minutes'] >= self.CLOCK_END_MIN
        c['expired'] = bool(expired)
        if expired:
            self.deadline_passed = True
        self._clock = c
        self._save_clock()
        return {'minutes': c['minutes'], 'display': self.clock_display(),
                'expired': expired}

    def get_time_until_deadline(self) -> Dict[str, Any]:
        """Get time remaining until trade deadline.

        On deadline day with the game clock running, the countdown follows
        the game clock (30-min increments toward 3 PM ET). Otherwise it
        falls back to the wall-clock estimate as before.
        """
        c = self._clock_store()
        if c.get('date') and not c.get('expired'):
            left = self.time_until_close()
            total_seconds = int(left.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            urgency = 'critical' if left <= timedelta(hours=1) else (
                'high' if left <= timedelta(hours=3) else 'medium')
            return {
                'expired': False,
                'time_left': left,
                'formatted': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
                'hours': hours, 'minutes': minutes, 'seconds': seconds,
                'urgency': urgency,
                'game_clock': self.clock_display(),
            }
        if c.get('expired'):
            return {'expired': True, 'time_left': timedelta(0),
                    'formatted': "DEADLINE PASSED", 'urgency': 'expired'}
        now = datetime.now()

        dd = self.deadline_date()
        today = now.date()
        if today > dd:
            # Next season has no schedule yet: fall back to the Mar-8
            # constant for the countdown target.
            dd = date(dd.year + 1, self.DEADLINE_MONTH, self.DEADLINE_DAY)
        if not self.is_trade_deadline_day(now):
            # Find next trade deadline
            next_deadline = datetime(dd.year, dd.month, dd.day,
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
    
    def _real_trade_counts(self) -> Dict[str, int]:
        """Real per-team trade counts from live league state.

        Combines this season's deadline activity log with completed
        trades recorded on the game manager's trade_history
        (trade_engine.CompletedTrade records). Only teams that exist in
        the live league are counted -- stray names never leak in.
        """
        counts: Dict[str, int] = {}
        real = {self._intel_team_name(t) for t in self._intel_teams()}

        def bump_all(names) -> None:
            clean = [str(n or "").strip() for n in (names or [])]
            clean = [n for n in clean if n]
            # All-or-nothing: a trade that names a club outside the
            # live league is not league activity (keeps this in sync
            # with _recent_real_trades).
            if clean and all(n in real for n in clean):
                for n in clean:
                    counts[n] = counts.get(n, 0) + 1

        try:
            for entry in (self.trade_activity_log or []):
                bump_all(entry.get("teams_involved", None))
        except Exception:
            pass
        try:
            history = getattr(self.game_manager, "trade_history", None) or []
            for tr in history:
                bump_all([getattr(tr, "team_a", ""),
                          getattr(tr, "team_b", "")])
        except Exception:
            pass
        return counts

    @staticmethod
    def _parse_trade_date(value) -> Any:
        """CompletedTrade.date is a free-form string; parse defensively."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day)
        if isinstance(value, str):
            text = value.strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
                try:
                    return datetime.strptime(text, fmt)
                except Exception:
                    continue
            try:
                return datetime.fromisoformat(text)
            except Exception:
                pass
        return None

    def _recent_real_trades(self, limit: int = 8) -> List[Dict[str, Any]]:
        """Newest-first list of real completed trades from live state.

        Merges this season's deadline activity log with the game
        manager's completed-trade history. Each item:
          {'ts': datetime|None, 'teams': [a, b], 'players': int,
           'summary': str}
        Only trades between teams that exist in the live league.
        Deterministic. Never raises.
        """
        real = {self._intel_team_name(t) for t in self._intel_teams()}
        items: List[Dict[str, Any]] = []

        def ok_teams(names):
            clean = [str(n or "").strip() for n in (names or [])]
            clean = [n for n in clean if n]
            if not clean:
                return []
            return clean if all(n in real for n in clean) else []

        try:
            for entry in (self.trade_activity_log or []):
                teams = ok_teams(entry.get("teams_involved"))
                if not teams:
                    continue
                ts = entry.get("timestamp")
                if not isinstance(ts, datetime):
                    ts = None
                try:
                    players = int(entry.get("players_count", 0) or 0)
                except Exception:
                    players = 0
                items.append({
                    "ts": ts,
                    "teams": teams,
                    "players": players,
                    "summary": str(entry.get("trade_type", "") or ""),
                })
        except Exception:
            pass
        try:
            history = getattr(self.game_manager, "trade_history", None) or []
            for tr in history:
                teams = ok_teams([getattr(tr, "team_a", ""),
                                  getattr(tr, "team_b", "")])
                if len(teams) < 2:
                    continue
                try:
                    players = (len(getattr(tr, "a_gave", None) or [])
                               + len(getattr(tr, "b_gave", None) or []))
                except Exception:
                    players = 0
                items.append({
                    "ts": self._parse_trade_date(getattr(tr, "date", "")),
                    "teams": teams,
                    "players": players,
                    "summary": str(getattr(tr, "summary", "") or ""),
                })
        except Exception:
            pass
        items.sort(key=lambda i: (i["ts"] is not None, i["ts"]),
                   reverse=True)
        return items[:max(0, int(limit or 0))]

    def generate_trade_activity(self) -> List[Dict]:
        """Deadline-day trade activity derived from REAL league state.

        Returns the most recent actual completed trades (this season's
        deadline log plus the game manager's completed-trade history),
        newest first, capped at 8. The dict shape is unchanged from
        before ('timestamp' datetime, 'type', 'description', 'impact',
        'teams_involved', 'urgency_level') so existing callers
        (trade_deadline_center.py, deadline.py paths) keep working.

        When no real trade has happened yet, the ticker gets explicitly
        labeled ESTIMATE projections grounded in real buyer-need /
        seller-asset matchups -- never fabricated deals presented as
        fact, never hardcoded NHL abbreviations, no random figures.
        """
        if not self.is_trade_deadline_day():
            return []

        time_info = self.get_time_until_deadline()
        if time_info.get('expired'):
            return []
        urgency = time_info.get('urgency', 'normal')

        def impact_for(players: int) -> str:
            if players >= 6:
                return 'huge'
            if players >= 4:
                return 'high'
            if players >= 2:
                return 'medium'
            return 'low'

        out: List[Dict] = []
        for item in self._recent_real_trades(limit=8):
            teams = item["teams"]
            summary = (item.get("summary") or "").strip()
            n = item["players"]
            detail = (summary if summary
                      else f"{n} player{'s' if n != 1 else ''} moved")
            out.append({
                'timestamp': item["ts"] or datetime.now(),
                'type': 'completed',
                'description': f"TRADE: {' ↔ '.join(teams)} — {detail}",
                'impact': impact_for(n),
                'teams_involved': list(teams),
                'urgency_level': urgency
            })
        if out:
            return out

        # No real trades yet: speculative projections, honestly labeled
        # (each _generate_trade_predictions description is already
        # prefixed ESTIMATE per the REV-F3 convention).
        for pred in self._generate_trade_predictions()[:4]:
            try:
                like = int(pred.get('likelihood', 0) or 0)
            except Exception:
                like = 0
            out.append({
                'timestamp': datetime.now(),
                'type': 'projection',
                'description': str(pred.get('description', '')),
                'impact': ('huge' if like >= 75 else 'high' if like >= 60
                           else 'medium' if like >= 50 else 'low'),
                'teams_involved': list(pred.get('teams_involved', [])),
                'urgency_level': urgency
            })
        return out

    def get_team_activity_status(self) -> Dict[str, Dict]:
        """Trading activity status for every team in the LIVE league.

        Keys are real team names (never hardcoded abbreviations);
        strategies come from the live buyer/seller standings split and
        activity from real completed trades. Value shape is unchanged:
        activity_level / indicator / strategy / recent_trades /
        status_text.
        """
        self._refresh_team_strategies()
        trade_counts = self._real_trade_counts()
        activity_status: Dict[str, Dict] = {}

        for team in self._intel_teams():
            name = self._intel_team_name(team)
            if name in activity_status:
                continue  # duplicate names: first wins, deterministic
            strategy = self.team_strategies.get(name, 'neutral')
            recent_activity = trade_counts.get(name, 0)

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

            activity_status[name] = {
                'activity_level': activity_level,
                'indicator': indicator,
                'strategy': strategy,
                'recent_trades': recent_activity,
                'status_text': (strategy.upper() if strategy != 'neutral'
                                else activity_level.upper())
            }

        return activity_status

    def _refresh_team_strategies(self) -> None:
        """Rebuild the team_strategies map from the LIVE standings.

        Buyers (top third by points) -> 'buying'; sellers (bottom
        third) -> 'selling'; everyone else -> 'neutral'. Refreshing on
        every read keeps strategies honest when standings move or the
        league is first attached after __init__ ran.
        """
        try:
            buyers, sellers = self._buyer_seller_split()
            buyer_names = {self._intel_team_name(t) for t in buyers}
            seller_names = {self._intel_team_name(t) for t in sellers}
            strategies: Dict[str, str] = {}
            for team in self._intel_teams():
                name = self._intel_team_name(team)
                if name in strategies:
                    continue
                if name in buyer_names:
                    strategies[name] = 'buying'
                elif name in seller_names:
                    strategies[name] = 'selling'
                else:
                    strategies[name] = 'neutral'
            self.team_strategies = strategies
        except Exception:
            pass

    def _initialize_team_strategies(self):
        """Initialize team trading strategies from live league state."""
        self._refresh_team_strategies()

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
        """Breaking news for deadline day, derived from REAL league state.

        Throttled (min 2 minutes between batches) as before; returns
        List[str] and appends to self.breaking_news. Items are built
        from actual completed trades, live standings, real trade counts,
        and the real deadline clock. Anything speculative carries the
        RUMOR (ESTIMATE) label. Deterministic -- no random selection;
        already-shown items are not repeated (bounded dedup set).
        """
        now = datetime.now()

        # Only generate breaking news on deadline day
        if not self.is_trade_deadline_day(now):
            return []

        # Check if enough time has passed since last news update
        if (now - self.last_breaking_news_check).total_seconds() < 120:  # 2 minutes minimum
            return []

        self.last_breaking_news_check = now

        shown = getattr(self, '_news_shown', None)
        if not isinstance(shown, set):
            shown = self._news_shown = set()

        time_info = self.get_time_until_deadline()
        formatted = str(time_info.get('formatted', ''))

        candidates: List[str] = []
        # Slightly wider than the throttle so a trade logged between
        # polls is never skipped.
        since = now - timedelta(seconds=130)

        # 1. Real trades completed since the last news check.
        for item in self._recent_real_trades(limit=8):
            ts = item.get("ts")
            if ts is None or ts < since:
                continue
            teams = item["teams"]
            n = item["players"]
            summary = (item.get("summary") or "").strip()
            detail = (summary if summary
                      else f"{n} player{'s' if n != 1 else ''} moved")
            candidates.append(f"TRADE: {' ↔ '.join(teams)} — {detail}")

        # 2. Live standings facts (never speculative).
        order = self._standings_order()
        if order:
            leader = order[0]
            pts = self._intel_points(leader)
            if pts > 0:
                candidates.append(
                    f"{self._intel_team_name(leader)} top the standings "
                    f"with {pts} points as the deadline clock ticks down "
                    f"({formatted} remaining).")

        # 3. Real busiest club from completed trades.
        counts = self._real_trade_counts()
        if counts:
            top_name, top_n = max(counts.items(),
                                  key=lambda kv: (kv[1], kv[0]))
            if top_n >= 1:
                candidates.append(
                    f"{top_name} {'is' if top_n == 1 else 'are'} the "
                    f"deadline's busiest club with {top_n} completed "
                    f"deal{'s' if top_n != 1 else ''}.")

        # 4. Speculative item, honestly labeled (already ESTIMATE).
        preds = self._generate_trade_predictions()
        if preds:
            candidates.append(
                f"RUMOR (ESTIMATE): {preds[0].get('description', '')}")

        # 5. Quiet day: fall back to the real deadline clock.
        if not candidates:
            candidates.append(
                f"Trade deadline day: {formatted} until the 3 PM deadline.")

        # Emit up to 3 new items, in deterministic priority order.
        news_items: List[str] = []
        for text in candidates:
            if text not in shown:
                shown.add(text)
                news_items.append(text)
                if len(news_items) >= 3:
                    break
        if len(shown) > 200:  # bounded dedup memory
            shown.clear()

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
    
    # ------------------------------------------------------------------
    # Market intelligence helpers — REV-F3 root-cause fix (Oct 11 2026).
    # Every figure below is derived from LIVE league state:
    #   - buyer/seller classification from real standings (points),
    #     never hardcoded team abbreviations;
    #   - cap figures from the real central cap accounting
    #     (Team.cap_space), never random.randint;
    #   - positional needs from real roster gap analysis;
    #   - timing patterns from the real trade activity log.
    # Trade predictions are grounded in real buyer-need / seller-asset
    # matchups and are explicitly labeled ESTIMATE — they are
    # speculation, not reported deals.
    # Return shapes are unchanged so native_ui/screens/deadline.py's
    # _MarketAnalyticsDialog keeps working.
    # ------------------------------------------------------------------

    def _intel_teams(self) -> List[Any]:
        """League team objects for intelligence. [] when unavailable."""
        try:
            league = getattr(self.game_manager, "league", None)
            teams = getattr(league, "teams", None) or []
            return [t for t in teams if t is not None]
        except Exception:
            return []

    @staticmethod
    def _intel_team_name(team) -> str:
        try:
            return str(getattr(team, "team_name", "") or "") or "Unknown"
        except Exception:
            return "Unknown"

    def _intel_points(self, team) -> int:
        """Live standings first (canonical sim state), team attr fallback."""
        try:
            league = getattr(self.game_manager, "league", None)
            entry = (getattr(league, "standings", None) or {}).get(
                self._intel_team_name(team))
            if isinstance(entry, dict):
                for key in ("Points", "points", "PTS", "pts"):
                    val = entry.get(key)
                    if isinstance(val, (int, float)):
                        return int(val)
        except Exception:
            pass
        try:
            return int(getattr(team, "points", 0) or 0)
        except Exception:
            return 0

    def _intel_wins(self, team) -> int:
        try:
            league = getattr(self.game_manager, "league", None)
            entry = (getattr(league, "standings", None) or {}).get(
                self._intel_team_name(team))
            if isinstance(entry, dict):
                for key in ("W", "w", "Wins", "wins"):
                    val = entry.get(key)
                    if isinstance(val, (int, float)):
                        return int(val)
        except Exception:
            pass
        try:
            return int(getattr(team, "wins", 0) or 0)
        except Exception:
            return 0

    def _intel_games_played(self, team) -> int:
        try:
            return int(getattr(team, "games_played", 0) or 0)
        except Exception:
            return 0

    def _intel_cap_space(self, team) -> int:
        """Real cap space via the central cap accounting (Team.cap_space)."""
        try:
            return int(getattr(team, "cap_space", 0) or 0)
        except Exception:
            return 0

    def _standings_order(self) -> List[Any]:
        """Teams sorted best-first by real points, wins as tiebreak."""
        teams = self._intel_teams()
        try:
            return sorted(
                teams,
                key=lambda t: (self._intel_points(t), self._intel_wins(t)),
                reverse=True)
        except Exception:
            return teams

    @staticmethod
    def _roster_counts(team) -> Dict[str, int]:
        """NHL-roster head counts by position group. Never raises."""
        counts = {"C": 0, "W": 0, "F": 0, "D": 0, "G": 0}
        try:
            for p in (getattr(team, "roster", None) or []):
                try:
                    pos = getattr(getattr(p, "primary_position", None),
                                  "value", "")
                    pos = str(pos or "").upper()
                except Exception:
                    continue
                if pos == "C":
                    counts["C"] += 1
                    counts["F"] += 1
                elif pos in ("LW", "RW"):
                    counts["W"] += 1
                    counts["F"] += 1
                elif pos in ("LD", "RD", "D"):
                    counts["D"] += 1
                elif pos == "G":
                    counts["G"] += 1
        except Exception:
            pass
        return counts

    def _team_needs(self, team) -> Dict[str, int]:
        """Positional shortfalls vs a standard NHL complement (12F/6D/2G)."""
        counts = self._roster_counts(team)
        return {
            "Forward": max(0, 12 - counts["F"]),
            "Defense": max(0, 6 - counts["D"]),
            "Goalie": max(0, 2 - counts["G"]),
        }

    def _team_primary_need(self, team) -> str:
        needs = self._team_needs(team)
        if not any(needs.values()):
            return "Depth"
        # Tie-break favors the scarcest real-world commodity first.
        best = max(needs.values())
        for key in ("Forward", "Defense", "Goalie"):
            if needs[key] == best:
                return key
        return "Depth"

    @staticmethod
    def _fmt_cap_m(dollars) -> str:
        """'$4.3M' style cap figure for UI display."""
        try:
            dollars = int(dollars or 0)
        except Exception:
            dollars = 0
        sign = "-" if dollars < 0 else ""
        return f"{sign}${abs(dollars) / 1_000_000:.1f}M"

    def _team_trade_counts(self) -> Dict[str, int]:
        """Real deadline-season trade counts per team from the activity log."""
        counts: Dict[str, int] = {}
        try:
            for entry in (self.trade_activity_log or []):
                for name in (entry.get("teams_involved", None) or []):
                    if name:
                        name = str(name)
                        counts[name] = counts.get(name, 0) + 1
        except Exception:
            pass
        return counts

    def _rental_assets(self, team, need_group=None) -> List[Dict[str, Any]]:
        """Expiring-contract players (years_remaining == 0), best-first.

        need_group: 'Forward' | 'Defense' | 'Goalie' | None (any group).
        These are the real rental chips a seller can offer.
        """
        want = {"Forward": "F", "Defense": "D", "Goalie": "G"}.get(need_group)
        assets: List[Dict[str, Any]] = []
        try:
            roster = getattr(team, "roster", None) or []
        except Exception:
            roster = []
        for p in roster:
            try:
                contract = getattr(p, "contract", None)
                years = int(getattr(contract, "years_remaining", 1) or 0)
                if years != 0:
                    continue
                pos = str(getattr(getattr(p, "primary_position", None),
                                  "value", "") or "").upper()
                group = ("F" if pos in ("C", "LW", "RW")
                         else "D" if pos in ("LD", "RD", "D")
                         else "G" if pos == "G" else "?")
                if want and group != want:
                    continue
                full_name = getattr(p, "full_name", None)
                if callable(full_name):
                    name = str(full_name())
                else:
                    name = (str(getattr(p, "first_name", "") or "") + " " +
                            str(getattr(p, "last_name", "") or "")).strip() or "?"
                ovr = int(getattr(p, "overall_rating", 0) or 0)
                assets.append({"name": name, "pos": pos or "?",
                               "ovr": ovr, "group": group})
            except Exception:
                continue
        assets.sort(key=lambda a: -a["ovr"])
        return assets

    def _seller_notable_assets(self, team) -> str:
        rentals = self._rental_assets(team)
        if rentals:
            top = rentals[0]
            return (f"Rental: {top['name']} ({top['pos']}, {top['ovr']} OVR)"
                    " — expiring contract")
        try:
            n_prospects = len(getattr(team, "prospects", None) or [])
        except Exception:
            n_prospects = 0
        if n_prospects:
            return "Prospect/pick inventory"
        return "Expiring contracts"

    def _rebuild_focus(self, team) -> str:
        try:
            n_prospects = len(getattr(team, "prospects", None) or [])
        except Exception:
            n_prospects = 0
        if n_prospects < 6:
            return "Prospects"
        if self._intel_cap_space(team) < 2_000_000:
            return "Picks"
        return "Youth"

    def _buyer_assets(self, team, space: int) -> str:
        try:
            n_prospects = len(getattr(team, "prospects", None) or [])
        except Exception:
            n_prospects = 0
        if space >= 8_000_000:
            return "Salary flexibility"
        if n_prospects >= 8:
            return "Rich in picks"
        return "Top prospects"

    def _intel_retention_used(self, team) -> int:
        """Active retained-salary transactions (NHL max is 3 per club)."""
        try:
            ledger = getattr(team, "retained_salary", None) or []
            used = 0
            for e in ledger:
                seasons = (e.get("seasons_remaining", 0)
                           if isinstance(e, dict) else 0)
                if int(seasons or 0) > 0:
                    used += 1
            return used
        except Exception:
            return 0

    def _intel_ltir(self, team) -> bool:
        """True when any roster player carries an LTIR designation."""
        try:
            for p in (getattr(team, "roster", None) or []):
                if str(getattr(p, "ir_status", "None") or "None") == "LTIR":
                    return True
        except Exception:
            pass
        return False

    def _buyer_seller_split(self) -> Tuple[List[Any], List[Any]]:
        """Top third of the real standings = buyers; bottom third = sellers.

        Sellers are ordered worst-first so the most desperate club leads.
        """
        order = self._standings_order()
        if not order:
            return [], []
        n = max(2, len(order) // 3)
        buyers = order[:n]
        sellers = list(reversed(order[-n:]))
        return buyers, sellers

    def _identify_buyer_teams(self) -> List[Dict[str, Any]]:
        """Buyers = top third of the real standings by points."""
        buyers, _ = self._buyer_seller_split()
        if not buyers:
            return []
        n = len(buyers)
        hot = max(2, n // 3)
        trade_counts = self._team_trade_counts()
        out = []
        for rank, team in enumerate(buyers, start=1):
            name = self._intel_team_name(team)
            space = self._intel_cap_space(team)
            recent = trade_counts.get(name, 0)
            out.append({
                'team': name,
                'likelihood': ('High' if rank <= hot
                               else 'Medium' if rank <= max(hot + 1, 2 * n // 3)
                               else 'Low'),
                'cap_space': self._fmt_cap_m(space),
                'primary_need': self._team_primary_need(team),
                'urgency': 'High' if rank <= hot else 'Medium',
                'assets': self._buyer_assets(team, space),
                'recent_activity': ('Very Active' if recent >= 2
                                    else 'Moderate' if recent == 1
                                    else 'Quiet'),
            })
        return out

    def _identify_seller_teams(self) -> List[Dict[str, Any]]:
        """Sellers = bottom third of the real standings by points."""
        _, sellers = self._buyer_seller_split()
        if not sellers:
            return []
        n = len(sellers)
        desperate = max(2, n // 3)
        out = []
        for idx, team in enumerate(sellers):
            out.append({
                'team': self._intel_team_name(team),
                'likelihood': ('High' if idx < desperate
                               else 'Medium' if idx < max(desperate + 1,
                                                          2 * n // 3)
                               else 'Low'),
                'notable_assets': self._seller_notable_assets(team),
                'asking_price': 'Flexible' if idx < desperate else 'Reasonable',
                'timeline': ('Immediate' if idx < max(1, n // 4)
                             else 'Before deadline'),
                'rebuild_focus': self._rebuild_focus(team),
            })
        return out

    def _analyze_position_needs(self) -> Dict[str, List[str]]:
        """Positional needs from real roster gap analysis (league-wide)."""
        needs = {"forwards": [], "defensemen": [], "goalies": [],
                 "depth": [], "rental_forwards": [],
                 "veteran_presence": []}
        scored = []
        rental_f = []
        for team in self._intel_teams():
            name = self._intel_team_name(team)
            gaps = self._team_needs(team)
            scored.append((name, gaps))
            f_rentals = self._rental_assets(team, "Forward")
            if f_rentals:
                rental_f.append((name, len(f_rentals)))
        for key, gkey in (("forwards", "Forward"), ("defensemen", "Defense"),
                          ("goalies", "Goalie")):
            ranked = sorted((s for s in scored if s[1][gkey] > 0),
                            key=lambda s: -s[1][gkey])
            needs[key] = [name for name, _ in ranked[:6]]
        # Depth: playoff-race clubs with no glaring positional hole still
        # shop for depth pieces.
        buyers = {b["team"] for b in self._identify_buyer_teams()}
        needs["depth"] = [name for name, gaps in scored
                          if name in buyers and not any(gaps.values())][:6]
        # Rental forwards: clubs holding the most expiring forward assets.
        rental_f.sort(key=lambda s: -s[1])
        needs["rental_forwards"] = [name for name, _ in rental_f[:6]]
        # Veteran presence: contenders with a young room (<3 skaters 32+).
        young_rooms = []
        for team in self._intel_teams():
            name = self._intel_team_name(team)
            if name not in buyers:
                continue
            vets = 0
            try:
                for p in (getattr(team, "roster", None) or []):
                    try:
                        if int(getattr(p, "age", 0) or 0) >= 32:
                            vets += 1
                    except Exception:
                        continue
            except Exception:
                pass
            if vets < 3:
                young_rooms.append((name, vets))
        young_rooms.sort(key=lambda s: s[1])
        needs["veteran_presence"] = [name for name, _ in young_rooms[:4]]
        return needs

    def _get_salary_cap_analysis(self) -> Dict[str, Dict]:
        """Real cap accounting for every league team.

        cap_space comes from Team.cap_space (the central cap system:
        waiver shed, retention, burial, dead cap). deadline_space is the
        standard accrued-space estimate: cap room prorated over the
        games remaining on an 82-game schedule.
        """
        analysis = {}
        for team in self._intel_teams():
            name = self._intel_team_name(team)
            try:
                hit = int(getattr(team, "payroll", 0) or 0)
            except Exception:
                hit = 0
            space = self._intel_cap_space(team)
            gp = self._intel_games_played(team)
            remaining = max(1, 82 - gp)
            dspace = int(space * 82 / remaining) if space > 0 else space
            analysis[name] = {
                'current_cap_hit': hit,
                'cap_space': space,
                'deadline_space': dspace,
                'flexibility': ('High' if space >= 10_000_000
                                else 'Medium' if space >= 4_000_000
                                else 'Low' if space > 0 else 'None'),
                'retention_slots': self._intel_retention_used(team),
                'ltir_available': self._intel_ltir(team),
            }
        return analysis

    def _generate_trade_predictions(self) -> List[Dict[str, Any]]:
        """Predictions grounded in real buyer-need / seller-asset matchups.

        Each pairs a top buyer's biggest positional shortfall with a
        seller's actual expiring-contract asset at that position. Every
        entry is explicitly marked ESTIMATE — this is speculation from
        live state, not reported trade talks.
        """
        buyers, sellers = self._buyer_seller_split()
        if len(buyers) < 1 or len(sellers) < 1:
            return []
        predictions = []
        used = set()
        for bi, bteam in enumerate(buyers[:5]):
            bname = self._intel_team_name(bteam)
            gaps = self._team_needs(bteam)
            need = (max(gaps, key=gaps.get) if any(gaps.values())
                    else "Depth")
            for srank, steam in enumerate(sellers[:5]):
                sname = self._intel_team_name(steam)
                if sname == bname:
                    continue  # tiny leagues overlap buyer/seller sets
                if (bname, sname) in used:
                    continue
                assets = self._rental_assets(steam, need if need != "Depth"
                                             else None)
                if not assets and need != "Depth":
                    assets = self._rental_assets(steam)
                if not assets:
                    continue
                used.add((bname, sname))
                top = assets[0]
                need_strength = gaps.get(need, 0) if need != "Depth" else 1
                like = min(85, 45 + need_strength * 4
                           + max(0, 4 - bi) * 3 + max(0, 3 - srank) * 2)
                predictions.append({
                    'likelihood': int(like),
                    'description': (
                        f"ESTIMATE — {bname} target {need.lower()} rental "
                        f"from {sname}"),
                    'teams_involved': [bname, sname],
                    'assets': (f"{top['name']} ({top['pos']}, {top['ovr']} OVR)"
                               f"; {sname} asking price: "
                               f"{'flexible' if srank < 2 else 'reasonable'}"),
                    'reasoning': (
                        f"Estimate from live standings: {bname} ranks "
                        f"#{bi + 1} by points with a {need.lower()} "
                        f"shortfall of {need_strength if need != 'Depth' else 'none — depth add'}; "
                        f"{sname} sits in the bottom third and holds "
                        f"expiring asset {top['name']}."),
                })
                break  # one prediction per buyer
        return predictions

    def _analyze_deadline_trends(self) -> Dict[str, Any]:
        """Deadline trends derived from live league state and the real
        trade activity log (no fabricated team lists, no random figures)."""
        needs = self._analyze_position_needs()
        buyers = self._identify_buyer_teams()
        sellers = self._identify_seller_teams()
        n_b, n_s = len(buyers), len(sellers)

        pos_counts = {k: len(needs[k]) for k in ("forwards", "defensemen",
                                                 "goalies")}
        most_key = (max(pos_counts, key=pos_counts.get)
                    if any(pos_counts.values()) else "forwards")
        most_label = {"forwards": "Forwards", "defensemen": "Defensemen",
                      "goalies": "Goalies"}[most_key]

        # Average deal size from trades actually logged this season.
        avg_size = "--"
        try:
            sizes = [int(e.get("players_count", 0) or 0)
                     for e in (self.trade_activity_log or [])
                     if int(e.get("players_count", 0) or 0) > 0]
            if sizes:
                avg_size = round(sum(sizes) / len(sizes), 1)
        except Exception:
            pass

        # Rental share: expiring vet assets vs futures inventory across
        # the league's sellers.
        rentals = futures = 0
        for team in self._intel_teams():
            try:
                expiring = len(self._rental_assets(team))
                prospects = len(getattr(team, "prospects", None) or [])
            except Exception:
                expiring, prospects = 0, 0
            rentals += expiring
            futures += prospects
        total_chips = rentals + futures
        rental_pct = (int(round(100 * rentals / total_chips))
                      if total_chips else 0)

        # Timing patterns from the real activity log: sellers that already
        # moved pieces are early movers; buyers already dealing are active.
        trade_counts = self._team_trade_counts()
        buyer_names = {b["team"] for b in buyers}
        seller_names = {s["team"] for s in sellers}
        early_movers = sorted(
            (n for n in seller_names if trade_counts.get(n, 0) > 0),
            key=lambda n: -trade_counts[n])[:4]
        deadline_active = sorted(
            (n for n in buyer_names if trade_counts.get(n, 0) > 0),
            key=lambda n: -trade_counts[n])[:4]

        sentiment = ("Aggressive buying by contenders" if n_b > n_s
                     else "Seller's market — asking prices soft" if n_s > n_b
                     else "Balanced market")

        return {
            'most_active_position': most_label,
            'average_trade_size': avg_size,
            'rental_vs_futures': {
                'rental': rental_pct,
                'futures': 100 - rental_pct
            },
            'price_trends': {
                'rentals': 'Increasing' if n_b >= n_s else 'Softening',
                'defensemen': ('Premium pricing'
                               if len(needs['defensemen']) > 3 else 'Stable'),
                'goalies': ('Heating up' if len(needs['goalies']) > 2
                            else 'Stable'),
                'picks': 'High demand' if n_s > n_b else 'Stable'
            },
            'timing_patterns': {
                'early_movers': early_movers,
                'deadline_day_active': deadline_active,
                'last_minute': [],
            },
            'market_sentiment': sentiment
        }

def get_deadline_manager(game_manager=None) -> TradeDeadlineManager:
    """Get singleton instance of trade deadline manager"""
    if not hasattr(get_deadline_manager, '_instance'):
        get_deadline_manager._instance = TradeDeadlineManager(game_manager)
    return get_deadline_manager._instance