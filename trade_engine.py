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

# Real OVR scale in-game: ~27 (fringe) to ~64 (superstar), median ~41.
POTENTIAL_BONUS = {'A': 220, 'B': 130, 'C': 50, 'D': 10, 'F': 0}


def player_trade_value(player) -> int:
    """Trade value of a player in 'pick points' (a 1st-round pick ~= 1000)."""
    ovr = player.overall_rating()
    base = max(0, (ovr - 30) * 30)  # 41 OVR -> 330, 52 OVR -> 660, 64 -> 1020

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
    expected = max(750_000, (ovr - 28) * 300_000)
    if salary > expected * 1.5:
        base *= 0.85
    elif salary < expected * 0.6 and ovr >= 50:
        base *= 1.1  # bargain deal

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
    ratio: float         # partner_value / user_value (AI's perspective)
    label: str           # 'Fair', 'You overpay', 'They overpay', ...
    user_cap_ok: bool = True
    partner_cap_ok: bool = True


def evaluate_trade(user_assets, partner_assets,
                   user_team=None, partner_team=None) -> TradeEvaluation:
    user_value = sum(asset_value(a) for a in user_assets)
    partner_value = sum(asset_value(a) for a in partner_assets)
    diff = user_value - partner_value
    ratio = (partner_value / user_value) if user_value else 0.0
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
                      user_team=None) -> AIResponse:
    """AI GM evaluates your offer. Returns accept / reject / counter."""
    from game_classes import DraftPick
    ev = evaluate_trade(user_assets, partner_assets)

    if not user_assets or not partner_assets:
        return AIResponse('reject', "There's nothing on the table yet.")

    # Cap reality check
    if not _cap_ok_after(partner_team, partner_assets, user_assets):
        return AIResponse('reject',
                          f"We can't make the money work under the cap.")

    ratio = ev.ratio  # value AI receives / value AI gives
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

    # Personality: some GMs drive a harder bargain
    greed = 0.95 + random.uniform(-0.03, 0.10)

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
    candidates = sorted(user_roster + user_picks, key=asset_value)
    shortfall = ev.user_value * greed - ev.partner_value
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
                  date_str="") -> CompletedTrade:
    """Move players and picks. Assumes the deal was accepted."""
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
    return CompletedTrade(date_str, user_team.team_name, partner_team.team_name,
                          a_labels, b_labels, summary)
