"""Trade engine for Puck Dynasty: valuation, AI negotiation, and execution.

Pure logic, no GUI. Powers the Trade Center window and draft-day trades.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------

# Real OVR scale in-game: ~62 (fringe) to ~90 (superstar), median ~76.
POTENTIAL_BONUS = {'A': 220, 'B': 130, 'C': 50, 'D': 10, 'F': 0}


def player_trade_value(player) -> int:
    """Trade value of a player in 'pick points' (a 1st-round pick ~= 1000)."""
    ovr = player.overall_rating()
    # 100-point scale: 68 OVR depth -> 300, 74 OVR starter -> 600,
    # 83 OVR elite -> 1050 (before age/potential multipliers)
    base = max(0, (ovr - 62) * 50)

    # Potential premium (matters most for young players)
    age = getattr(player, 'age', 27)
    pot = POTENTIAL_BONUS.get(getattr(player, 'potential_grade', 'F'), 0)
    if age <= 23:
        base += pot
    elif age <= 26:
        base += pot // 2

    # Age curve
    if age <= 21:
        base *= 1.3
    elif 24 <= age <= 29:
        base *= 1.2
    elif age >= 35:
        base *= 0.5
    elif age >= 33:
        base *= 0.8

    # Contract efficiency: overpaid players are worth less
    salary = getattr(player, 'salary', 0) or 0
    # Expected salary mirrors the market-value curve (100-point scale)
    expected = max(750_000, (ovr - 60) * 250_000)
    if salary > expected * 1.5:
        base *= 0.85
    elif salary < expected * 0.6 and ovr >= 70:
        base *= 1.1  # bargain deal

    # Volatility tax: hotheads cost less, but a superstar is worth the headache.
    try:
        import reputation_system as _rs
        base *= _rs.volatility_trade_discount(player)
    except Exception:
        pass

    # Goalies: fewer roster spots, slight premium for starters
    try:
        from game_classes import PlayerPosition
        if player.primary_position == PlayerPosition.GOALIE and ovr >= 48:
            base *= 1.15
    except Exception:
        pass

    return max(10, int(base))


def pick_trade_value(pick) -> int:
    """Trade value of a draft pick, refined from DraftPick.value."""
    try:
        base = pick.value
    except Exception:
        base = 100
    # Known high picks are worth more than the round average
    overall = getattr(pick, 'overall_pick', 0) or 0
    if overall and 1 <= overall <= 10:
        base = int(base * (1.6 - overall * 0.06))  # 1st overall ~= 1.54x
    return max(25, int(base))


def asset_label(asset) -> str:
    """Human label for a player or pick asset."""
    from game_classes import DraftPick
    if isinstance(asset, DraftPick):
        return asset.description
    try:
        return f"{asset.full_name} ({asset.primary_position.value}, {asset.overall_rating()} OVR)"
    except Exception:
        return str(asset)


def asset_value(asset) -> int:
    from game_classes import DraftPick
    return pick_trade_value(asset) if isinstance(asset, DraftPick) else player_trade_value(asset)


# ---------------------------------------------------------------------------
# Team needs
# ---------------------------------------------------------------------------

def team_needs(team) -> List[str]:
    """Return position groups sorted weakest-first, e.g. ['C', 'RD', 'G']."""
    from game_classes import PlayerPosition
    groups = {'LW': [], 'C': [], 'RW': [], 'LD': [], 'RD': [], 'G': []}
    for p in getattr(team, 'roster', []):
        try:
            pos = p.primary_position.value
        except Exception:
            continue
        key = 'G' if pos == 'G' else pos
        if key in groups:
            groups[key].append(p.overall_rating())
    strength = {}
    for pos, ovrs in groups.items():
        ovrs = sorted(ovrs, reverse=True)
        top = ovrs[:2] if pos != 'G' else ovrs[:1]
        strength[pos] = sum(top) / len(top) if top else 0
    return sorted(strength, key=lambda k: strength[k])


# ---------------------------------------------------------------------------
# Evaluation + AI negotiation
# ---------------------------------------------------------------------------

@dataclass
class TradeEvaluation:
    user_value: int
    partner_value: int
    diff: int            # positive => user overpays
    ratio: float         # user_value / partner_value (value AI receives / value AI gives)
    label: str           # 'Fair', 'You overpay', 'They overpay', ...
    user_cap_ok: bool = True
    partner_cap_ok: bool = True


def scout_adjusted_value(player, team) -> int:
    """Trade value through a team's scouts' eyes (AI parity with the user).

    The user reads scout tips in the news feed and adjusts their own
    valuation by hand. AI GMs get the same ability mechanically:
    - A scout buy-tip on an incoming target: the AI sees the hidden
      value and prices him closer to it (won't sell low on a find they
      spotted, will pay up for one).
    - A scout sell-tip on one of their own: the AI sees regression
      coming and shops him while the league still sees surface stats.

    The edge scales with the scout's JPA -- an elite scout's read moves
    the needle more than a guess from a bad one. Bad scouts' ghost tips
    can mislead the AI exactly like they mislead a trusting human GM.

    Market ecology (wave 1): the edge is then scaled by the club's
    analytics_philosophy (0-100). An analytics-heavy front office
    prices process metrics aggressively; an old-school room mostly
    trusts the surface numbers. Each club keeps its own formula --
    the league never converges.
    """
    base = player_trade_value(player)
    try:
        pid = getattr(player, "id", id(player))
        buy_tips = getattr(team, "scout_buy_tips", None) or {}
        sell_tips = getattr(team, "scout_sell_tips", None) or {}
        # Organizational philosophy: how much this front office trusts
        # process metrics. 0.05 (old-school) .. 0.95 (analytics-heavy).
        philo = max(0.05, min(0.95,
                              float(getattr(team, "analytics_philosophy",
                                            30.0) or 30.0) / 100.0))
        tip = buy_tips.get(pid)
        if tip is not None:
            jpa = tip.get("jpa", 10)
            # Elite eye: +25%; good: +15%; average: +8%; poor: +4%
            edge = 0.04 + 0.21 * (min(20, max(1, jpa)) - 1) / 19.0
            return int(base * (1.0 + edge * philo))
        tip = sell_tips.get(pid)
        if tip is not None:
            jpa = tip.get("jpa", 10)
            edge = 0.04 + 0.16 * (min(20, max(1, jpa)) - 1) / 19.0
            return int(base * (1.0 - edge * philo))
    except Exception:
        pass
    return base


def evaluate_trade(user_assets, partner_assets,
                   user_team=None, partner_team=None) -> TradeEvaluation:
    user_value = sum(asset_value(a) for a in user_assets)
    partner_value = sum(asset_value(a) for a in partner_assets)
    diff = user_value - partner_value
    ratio = (user_value / partner_value) if partner_value else 0.0
    if not user_assets or not partner_assets:
        label = "Incomplete"
    elif abs(diff) <= max(60, user_value * 0.08):
        label = "Fair deal"
    elif diff > 0:
        label = "You overpay"
    else:
        label = "They overpay"
    return TradeEvaluation(user_value, partner_value, diff, ratio, label)


def _cap_ok_after(team, outgoing, incoming) -> bool:
    try:
        cap = team.salary_cap
        payroll = team.payroll
    except Exception:
        return True
    out_sal = sum(getattr(p, 'salary', 0) or 0 for p in outgoing
                  if not _is_pick(p))
    in_sal = sum(getattr(p, 'salary', 0) or 0 for p in incoming
                 if not _is_pick(p))
    return (payroll - out_sal + in_sal) <= cap


def _is_pick(asset) -> bool:
    from game_classes import DraftPick
    return isinstance(asset, DraftPick)


@dataclass
class AIResponse:
    decision: str  # 'accept', 'reject', 'counter'
    message: str
    # For counters: assets the AI wants ADDED to your offer, or will add itself
    want_added: list = field(default_factory=list)
    will_add: list = field(default_factory=list)


def ai_consider_trade(partner_team, user_assets, partner_assets,
                      user_team=None, patience=1.0, situational=None) -> AIResponse:
    """AI GM evaluates your offer. Returns accept / reject / counter.

    patience: 1.0 = fresh talks. Drops each counter round; a tired GM
    drives a harder bargain (higher effective greed) and is likelier
    to walk away than counter.

    situational: optional dict from trade_storylines.situational_context()
    with a 'greed_mult' nudge (<1 = more eager, >1 = harder bargain).
    Purely additive -- None means classic behavior.
    """
    from game_classes import DraftPick
    ev = evaluate_trade(user_assets, partner_assets)

    # Scout-adjusted valuation: the AI GM sees tipped players through
    # their scouts' eyes, exactly like a human reading the news feed.
    # A buy-tip on an incoming target raises what the AI thinks he's
    # worth (they won't give him up cheap / will pay for hidden value);
    # a sell-tip on their own outgoing piece lowers it (happy to move
    # a regression candidate at surface price).
    try:
        adj_incoming = sum(
            scout_adjusted_value(a, partner_team) if not _is_pick(a)
            else asset_value(a) for a in user_assets)
        adj_outgoing = sum(
            scout_adjusted_value(a, partner_team) if not _is_pick(a)
            else asset_value(a) for a in partner_assets)
        _scout_ratio = (adj_incoming / adj_outgoing) if adj_outgoing else 0.0
        # Blend: scouts inform but don't override the base valuation.
        ratio = 0.5 * ev.ratio + 0.5 * _scout_ratio
    except Exception:
        ratio = ev.ratio

    if not user_assets or not partner_assets:
        return AIResponse('reject', "There's nothing on the table yet.")

    # Cap reality check
    if not _cap_ok_after(partner_team, partner_assets, user_assets):
        return AIResponse('reject',
                          f"We can't make the money work under the cap.")

    # (ratio already scout-blended above)
    needs = team_needs(partner_team)
    # AI likes getting help at weak positions
    need_bonus = 0.0
    for a in user_assets:
        if _is_pick(a):
            continue
        try:
            if a.primary_position.value in needs[:2]:
                need_bonus += 0.04
        except Exception:
            pass
    effective = ratio + need_bonus

    # Personality: some GMs drive a harder bargain. Low patience
    # (after several counter rounds) pushes the demand higher and can
    # turn a would-be counter into a flat rejection.
    greed = (0.95 + random.uniform(-0.03, 0.10)) / max(patience, 0.35)
    # Situational nudge (standings stance, streaks, rivalries, deadline
    # urgency). Additive only; absent without a context dict.
    sit_mult = 1.0
    if isinstance(situational, dict):
        try:
            sit_mult = float(situational.get('greed_mult', 1.0))
        except Exception:
            sit_mult = 1.0
    greed *= sit_mult

    if effective >= greed:
        return AIResponse('accept', "You've got a deal.")

    # Build a counter: find the smallest user asset that balances it
    user_roster = [p for p in getattr(user_team, 'roster', [])
                   if p not in user_assets] if user_team else []
    user_picks = []
    if user_team:
        try:
            year = None
            for p in user_roster:
                pass
            picks_by_year = getattr(user_team, 'draft_picks', {})
            for yr, picks in picks_by_year.items():
                for pk in picks:
                    if getattr(pk, 'current_team', '') == getattr(user_team, 'team_name', ''):
                        user_picks.append(pk)
        except Exception:
            pass
    if patience < 0.55 and random.random() < (0.55 - patience):
        return AIResponse('reject',
                          "We've been around on this too long. I'm moving on.")
    candidates = sorted(user_roster + user_picks, key=asset_value)
    shortfall = ev.partner_value * greed - ev.user_value
    for c in candidates:
        if asset_value(c) >= shortfall * 0.7:
            return AIResponse(
                'counter',
                f"Not quite. Throw in {asset_label(c)} and we have a deal.",
                want_added=[c])

    # Or the AI offers to sweeten from its side if you're close
    if effective >= greed - 0.15:
        partner_roster = [p for p in getattr(partner_team, 'roster', [])
                          if p not in partner_assets]
        sweeteners = sorted(partner_roster, key=asset_value)
        for s in sweeteners[:3]:
            if asset_value(s) < ev.diff * -0.5 + 200:
                return AIResponse(
                    'counter',
                    f"We're close. If you take {asset_label(s)} too, I'll do it.",
                    will_add=[s])

    return AIResponse('reject',
                      "We're too far apart on value. Come back with a real offer.")


# ---------------------------------------------------------------------------
# Execution + history
# ---------------------------------------------------------------------------

@dataclass
class CompletedTrade:
    date: str
    team_a: str
    team_b: str
    a_gave: List[str]
    b_gave: List[str]
    summary: str


def execute_trade(user_team, partner_team, user_assets, partner_assets,
                  date_str="", league=None, board=None) -> CompletedTrade:
    """Move players and picks. Assumes the deal was accepted.

    league/board are optional: when provided (user-involved deals), the
    trade's fallout is scored -- GM stature moves, the fleeced GM holds a
    personal grudge, and the board logs it via record_big_event. The asset
    movement itself is untouched.
    """
    from game_classes import DraftPick
    for a in user_assets:
        if isinstance(a, DraftPick):
            a.current_team = partner_team.team_name
        else:
            user_team.remove_player(a)
            partner_team.add_player(a)
    for a in partner_assets:
        if isinstance(a, DraftPick):
            a.current_team = user_team.team_name
        else:
            partner_team.remove_player(a)
            user_team.add_player(a)

    a_labels = [asset_label(a) for a in user_assets]
    b_labels = [asset_label(a) for a in partner_assets]
    summary = (f"{user_team.team_name} acquires {', '.join(b_labels)} from "
               f"{partner_team.team_name} for {', '.join(a_labels)}.")
    # GM stature fallout: the league saw this deal. A fleece builds the
    # winner's "shark" reputation but the loser holds a personal grudge;
    # getting worked costs stature; fair dealing builds trust both ways.
    # Additive -- asset movement above is untouched.
    try:
        from reputation_system import record_trade_outcome
        ev = evaluate_trade(user_assets, partner_assets)
        partner_ratio = float(ev.ratio) if ev.ratio else 1.0
        user_ratio = (1.0 / partner_ratio) if partner_ratio > 0 else 1.0
        record_trade_outcome(league, user_team, partner_team, user_ratio,
                             board_a=board)
    except Exception:
        pass
    # Authoritative post-trade integration point: EVERY completed trade
    # path (user deals, AI deadline deals) flows through here.
    #  - Fresh start: rescued players get their morale payoff.
    #  - Steal watch: scout-tipped acquisitions are tracked until their
    #    post-trade production validates (or quietly expires) the call.
    # Both are idempotent per trade via the _trade_stamp key.
    try:
        _post_trade_effects(user_team, partner_team, user_assets,
                            partner_assets, date_str, league)
    except Exception:
        pass
    return CompletedTrade(date_str, user_team.team_name, partner_team.team_name,
                          a_labels, b_labels, summary)


def _post_trade_effects(user_team, partner_team, user_assets, partner_assets,
                        date_str, league) -> None:
    """One integration point for all post-trade effects. Idempotent."""
    from game_classes import DraftPick
    try:
        import reputation_system as _rs
    except ImportError:
        return
    teams = []
    try:
        teams = list(getattr(league, "teams", []) or [])
    except Exception:
        pass
    if not teams:
        teams = [user_team, partner_team]
    # (incoming players, old team, new team) for both directions
    moves = []
    for a in partner_assets:
        if not isinstance(a, DraftPick):
            moves.append((a, partner_team, user_team))
    for a in user_assets:
        if not isinstance(a, DraftPick):
            moves.append((a, user_team, partner_team))
    for player, old_team, new_team in moves:
        try:
            stamp = (date_str,
                     getattr(old_team, "team_name", ""),
                     getattr(new_team, "team_name", ""))
            if getattr(player, "_trade_stamp", None) == stamp:
                continue  # already processed for this trade
            player._trade_stamp = stamp
        except Exception:
            pass
        # Fresh start: the rescue payoff.
        try:
            _rs.apply_fresh_start(player, old_team, new_team, teams=teams)
        except Exception:
            pass
        # Dressing-room cascade (module 03): the old room reacts to the
        # departure, the new room absorbs the arrival.
        try:
            import dressing_room as _dr
            _dr.cascade_on_trade(old_team, traded=player, date_str=date_str)
            _dr.cascade_on_trade(new_team, arriving=player, date_str=date_str)
        except Exception:
            pass
        # Steal watch: was this player scout-tipped to the acquiring team?
        try:
            pid = getattr(player, "id", id(player))
            tips = getattr(new_team, "scout_buy_tips", None) or {}
            tip = tips.get(pid)
            if tip is not None:
                enriched = dict(tip)
                enriched.setdefault("signals", [])
                enriched.setdefault("value_score", 0.0)
                enriched["selling_team"] = getattr(
                    old_team, "team_name", "")
                _rs.watch_steal_candidate(player, new_team, enriched,
                                          date_str)
                # The watch owns this call now: mark the ledger read
                # acted-on so the monthly grader never grades it twice.
                try:
                    import analytics_scouting as _as
                    _as.mark_tip_acted_on(new_team, "buy", pid,
                                          date_str)
                except Exception:
                    pass
        except Exception:
            pass
        # Sell watch: did the SELLING team's scout flag this player as a
        # regression candidate? If his production collapses in the new
        # uniform, the scout called the peak.
        try:
            pid = getattr(player, "id", id(player))
            stips = getattr(old_team, "scout_sell_tips", None) or {}
            stip = stips.get(pid)
            if stip is not None:
                senriched = dict(stip)
                senriched.setdefault("signals", [])
                _rs.watch_sell_candidate(player, old_team, new_team,
                                         senriched, date_str)
                try:
                    import analytics_scouting as _as
                    _as.mark_tip_acted_on(old_team, "sell", pid,
                                          date_str)
                except Exception:
                    pass
        except Exception:
            pass
