# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Player-side contract decisions: how UFAs and RFAs weigh offers.

The other half of the market. rfa_system.py (and the FA views) decide what
teams OFFER; this module decides what players SIGN. Every factor the design
calls for lives here:

  - talent / archetype / personality (what he is, what he wants to be)
  - situation (role, team trajectory, happiness, tenure)
  - loyalty attribute (staying vs chasing)
  - ambition/focus: cup | money | ice_time | stability | home -- and which
    team fits that ambition best
  - nationality / hometown pull
  - favoured and rival players on the roster (relationships), family
  - bad blood: signing with a hated rival, scaled by how much the fans who
    loved him would turn. Some players embrace the villain role; most don't.

The output is an appeal score (0..1) plus human-readable reasons, so the UI
can show *why* a player is keen or cold. Old-save safe: every field is
seeded lazily on first read.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Ambitions
# ---------------------------------------------------------------------------

AMBITION_CUP = "cup"            # ring-chaser: contention above all
AMBITION_MONEY = "money"        # mercenary: show me the dollars
AMBITION_ICE = "ice_time"       # wants a bigger role / top-six minutes
AMBITION_STABILITY = "stability"  # loyal lifer: stay, security, comfort
AMBITION_HOME = "home"          # wants to play at/near home

AMBITIONS = (AMBITION_CUP, AMBITION_MONEY, AMBITION_ICE,
             AMBITION_STABILITY, AMBITION_HOME)

# Per-ambition weights over the appeal factors. Each row sums ~1.0; the
# bad-blood cost is subtractive on top (a veto, not a preference).
_WEIGHTS = {
    AMBITION_CUP:       dict(money=0.15, cup=0.45, ice=0.10, stay=0.10,
                             home=0.05, people=0.10),
    AMBITION_MONEY:     dict(money=0.50, cup=0.10, ice=0.10, stay=0.10,
                             home=0.03, people=0.07),
    AMBITION_ICE:       dict(money=0.20, cup=0.10, ice=0.40, stay=0.10,
                             home=0.05, people=0.10),
    AMBITION_STABILITY: dict(money=0.25, cup=0.10, ice=0.10, stay=0.30,
                             home=0.05, people=0.15),
    AMBITION_HOME:      dict(money=0.20, cup=0.10, ice=0.10, stay=0.15,
                             home=0.30, people=0.10),
}


# ---------------------------------------------------------------------------
# Field seeding (old-save safe)
# ---------------------------------------------------------------------------

def _roll_ambition(player) -> str:
    """Seed ambition from career stage + personality, the way real players
    sort themselves: kids want ice, primes want money/cups, vets chase."""
    age = int(getattr(player, "age", 27) or 27)
    controversy = int(getattr(player, "controversy", 0) or 0)
    loyalty = int(getattr(player, "loyalty", 50) or 50)
    r = random.random()
    if age <= 24:
        # kids want opportunity first, then the bag
        if r < 0.45: return AMBITION_ICE
        if r < 0.70: return AMBITION_MONEY
        if r < 0.85: return AMBITION_CUP
        return AMBITION_STABILITY
    if age <= 30:
        if controversy >= 60 and r < 0.55: return AMBITION_MONEY
        if r < 0.35: return AMBITION_MONEY
        if r < 0.62: return AMBITION_CUP
        if r < 0.77: return AMBITION_ICE
        if loyalty >= 65: return AMBITION_STABILITY
        return AMBITION_HOME if r < 0.90 else AMBITION_STABILITY
    # 31+: the window is closing
    if r < 0.45: return AMBITION_CUP
    if r < 0.65: return AMBITION_STABILITY
    if r < 0.78: return AMBITION_MONEY
    if r < 0.90: return AMBITION_HOME
    return AMBITION_ICE


def ensure_decision_fields(player) -> None:
    """Stamp loyalty + ambition if missing (new saves seed at generation;
    old saves pick them up lazily here)."""
    if getattr(player, "loyalty", None) is None:
        teamwork = int(getattr(player, "teamwork", 50) or 50)
        leadership = int(getattr(player, "leadership", 50) or 50)
        base = 0.6 * 50 + 0.25 * teamwork + 0.15 * leadership
        player.loyalty = max(1, min(99, int(random.gauss(base, 15))))
    if getattr(player, "ambition", None) not in AMBITIONS:
        # staff also carry an 'ambition' attr with different values; only
        # stamp players (they lack 'control_need').
        if getattr(player, "control_need", None) is None:
            player.ambition = _roll_ambition(player)


def seed_league_decision_fields(league) -> None:
    """Bulk-seed every skater/goalie once (cheap; idempotent)."""
    for team in getattr(league, "teams", []) or []:
        for p in list(getattr(team, "roster", []) or []):
            try:
                ensure_decision_fields(p)
            except Exception:
                continue
    for p in list(getattr(league, "free_agents", []) or []):
        try:
            ensure_decision_fields(p)
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _name(x) -> str:
    return str(getattr(x, "name", "Unknown"))


def previous_team(player, league) -> Optional[Any]:
    """The club he played for last (for the bad-blood / loyalty math).

    Stamped as ``player.last_team_name`` whenever he leaves a roster
    (Team.remove_player); falls back to his current team_name when he is
    still on a roster. None when genuinely unknown (old saves).
    """
    ltn = getattr(player, "last_team_name", "") or ""
    teams = list(getattr(league, "teams", []) or [])
    if ltn and ltn != "Free Agent":
        for t in teams:
            if _name(t) == ltn or getattr(t, "team_name", "") == ltn:
                return t
    cur = getattr(player, "team_name", "") or ""
    if cur and cur != "Free Agent":
        for t in teams:
            if _name(t) == cur or getattr(t, "team_name", "") == cur:
                return t
    return None


def _ovr(player) -> float:
    try:
        return float(player.overall_rating())
    except Exception:
        return 75.0


def _market_value(player) -> int:
    try:
        from windows import ContractNegotiationView
        v = ContractNegotiationView._estimate_market_value(player)
        if v:
            return int(v)
    except Exception:
        pass
    return int(max(750_000, (_ovr(player) - 60) * 250_000))


def _team_strength(team, league) -> float:
    """0..1 contention signal: last season's pace, else roster talent."""
    try:
        standings = getattr(league, "standings", None)
        if standings:
            for row in standings:
                nm = row.get("team") if isinstance(row, dict) else getattr(row, "team", None)
                if nm in (_name(team), getattr(team, "abbreviation", "")):
                    gp = (row.get("gp") if isinstance(row, dict)
                          else getattr(row, "gp", 82)) or 82
                    pts = (row.get("points") if isinstance(row, dict)
                           else getattr(row, "points", 82)) or 0
                    return max(0.0, min(1.0, (pts / max(1, gp)) / 1.45))
    except Exception:
        pass
    try:
        ovrs = sorted((_ovr(p) for p in (getattr(team, "roster", []) or [])),
                      reverse=True)[:18]
        if ovrs:
            return max(0.0, min(1.0, (sum(ovrs) / len(ovrs) - 68) / 22))
    except Exception:
        pass
    return 0.5


def _position_group(player) -> str:
    pos = str(getattr(player, "primary_position", "") or "").upper()
    if "G" in pos and len(pos) <= 2:
        return "G"
    if pos.startswith("D"):
        return "D"
    return "F"


def _projected_role(player, team) -> Tuple[float, str]:
    """Where he'd slot in this lineup: 1.0 = top line/pair/starter."""
    group = _position_group(player)
    mine = _ovr(player)
    try:
        peers = sorted(
            (_ovr(p) for p in (getattr(team, "roster", []) or [])
             if _position_group(p) == group and p is not player),
            reverse=True)
    except Exception:
        peers = []
    slot = sum(1 for o in peers if o > mine)  # 0-based depth slot
    if group == "G":
        score, label = (1.0, "the starter") if slot == 0 else \
                      (0.55, "the backup") if slot == 1 else (0.2, "third-string")
    elif group == "D":
        score, label = (1.0, "a top-pair role") if slot <= 1 else \
                      (0.7, "a second-pair role") if slot <= 3 else \
                      (0.45, "a third-pair role") if slot <= 5 else \
                      (0.25, "a depth role")
    else:
        score, label = (1.0, "a first-line role") if slot <= 2 else \
                      (0.75, "a top-six role") if slot <= 5 else \
                      (0.5, "a middle-six role") if slot <= 8 else \
                      (0.3, "a bottom-six role")
    return score, label


def _tenure(player, team) -> float:
    try:
        import reputation_system as _rs
        yrs = _rs._tenure_years(player)
        return float(yrs or 0)
    except Exception:
        return 0.0


def _hometown_pull(player, team) -> Tuple[float, Optional[str]]:
    """1.0 if the team plays in his hometown; nationality alone is a whisper."""
    city = str(getattr(team, "city", "") or "").strip().lower()
    if not city:
        return 0.0, None
    birthplace = str(getattr(player, "birthplace", "") or "").lower()
    if city and city in birthplace:
        tname = _name(team)
        return 1.0, f"it's home -- {tname} play in his hometown"
    return 0.0, None


def _people_pull(player, team) -> Tuple[float, List[str]]:
    """Favoured/rival players already in that room; family counts double."""
    score = 0.0
    reasons: List[str] = []
    try:
        rels = getattr(player, "relationships", {}) or {}
        fam = set(getattr(player, "family_ids", []) or [])
        roster_ids = {getattr(p, "id", None):
                      getattr(p, "full_name", getattr(p, "name", "?"))
                      for p in (getattr(team, "roster", []) or [])}
        friends = rivals = 0
        for pid, nm in roster_ids.items():
            if pid is None:
                continue
            if pid in fam:
                score += 0.20
                reasons.append(f"his family ({nm}) is there")
                continue
            v = rels.get(pid, 0)
            if v >= 60:
                score += 0.08
                friends += 1
            elif v <= -60:
                score -= 0.12
                rivals += 1
        if friends:
            reasons.append(f"{friends} close friend{'s' if friends > 1 else ''} in the room")
        if rivals:
            reasons.append(f"bad blood with {rivals} player{'s' if rivals > 1 else ''} there")
    except Exception:
        pass
    return max(-0.35, min(0.35, score)), reasons


def _ledger(app) -> Any:
    try:
        from main import get_ledger
        return get_ledger(app)
    except Exception:
        return None


def _rival_move_cost(player, from_team, to_team, app) -> Tuple[float, Optional[str]]:
    """Bad-blood veto: signing with a hated rival, scaled by how much the
    fans who loved him would turn. Villains (high controversy) and
    mercenaries care less; loyal fan favourites care most."""
    if from_team is None or to_team is None or from_team is to_team:
        return 0.0, None
    heat = 0.0
    try:
        lg = _ledger(app)
        if lg is not None:
            heat = float(lg.memory_weight(_name(from_team), _name(to_team)) or 0)
    except Exception:
        heat = 0.0
    if heat < 15:
        return 0.0, None
    fan_love = 0.0
    try:
        import reputation_system as _rs
        fan_love = float(_rs.fan_favourite_score(player, from_team).get("score", 0))
    except Exception:
        fan_love = 0.0
    controversy = float(getattr(player, "controversy", 0) or 0)
    ambition = getattr(player, "ambition", AMBITION_STABILITY)
    # the turn: how vicious the betrayal narrative would be. Convex in both
    # inputs -- a mild rivalry or a replaceable player is a wrinkle; a
    # beloved star crossing a hot rivalry is the back page for a month.
    heat_f = (heat / 100.0) ** 1.2
    love_f = 0.20 + 0.80 * (min(1.0, fan_love / 100.0) ** 1.5)
    betrayal = heat_f * love_f
    mod = 1.0 - 0.5 * min(1.0, controversy / 100.0)  # villains shrug
    if ambition == AMBITION_MONEY:
        mod *= 0.5  # mercenaries don't read the papers
    cost = min(0.40, betrayal * mod)
    if cost < 0.05:
        return 0.0, None
    reason = (f"the {_name(from_team)} fans adore him -- signing with "
              f"hated rival {_name(to_team)} would make him the villain")
    if fan_love < 40:
        reason = (f"bad blood between {_name(from_team)} and {_name(to_team)} "
                  f"gives him pause")
    return cost, reason


# ---------------------------------------------------------------------------
# The appeal model
# ---------------------------------------------------------------------------

def contract_appeal(player, team, aav: int, years: int, *,
                    current_team=None, league=None, app=None,
                    is_offer_sheet: bool = False,
                    market_mult: float = 1.0,
                    signing_bonus: int = 0,
                    ) -> Tuple[float, List[str]]:
    """0..1 appeal of (team, aav, years) to this player + top reasons.

    current_team: the club he'd be leaving (None for long-time free agents).
    market_mult: scales his market ask (e.g. a disrespected GM pays a
    dysfunction premium -- the same dollar is worth less from that club).
    signing_bonus: annual signing bonus (part of the AAV). Players prefer
    cash upfront -- a bonus-heavy offer beats straight salary at the same
    AAV (lockout protection, immediate money).
    """
    ensure_decision_fields(player)
    ambition = getattr(player, "ambition", AMBITION_STABILITY)
    if ambition not in _WEIGHTS:
        ambition = AMBITION_STABILITY
    w = _WEIGHTS[ambition]
    age = int(getattr(player, "age", 27) or 27)
    loyalty = float(getattr(player, "loyalty", 50) or 50)
    happiness = float(getattr(player, "happiness", 70) or 70)
    market = int(_market_value(player) * max(0.5, market_mult))

    reasons: List[str] = []
    parts: Dict[str, float] = {}

    # --- money + term security -------------------------------------------
    ratio = (aav / max(1, market))
    # BUG-021: the old curve ((ratio-0.65)/0.65) left money_score at 0.54 for
    # a full-market offer and let 50%-of-market offers ride on the other
    # parts -- UFAs signed at half price ~1 in 3. Full market now scores 1.0.
    money_score = max(0.0, min(1.2, (ratio - 0.55) / 0.45))
    ideal = 7 if age <= 26 else 5 if age <= 30 else 3
    term_score = max(0.0, 1.0 - abs(years - ideal) / 6.0)
    if years >= 4 and age <= 30:
        term_score = min(1.0, term_score + 0.15)  # security matters young
    # ring-chasers take the discount; everyone else wants to be paid
    if ambition == AMBITION_CUP and age >= 32 and ratio < 1.0:
        money_score = max(money_score, 0.55)
        reasons.append("he'll take less for a real shot at the Cup")
    parts["money"] = 0.7 * money_score + 0.3 * term_score
    # Signing bonus: cash upfront beats deferred salary at the same AAV.
    # A fully bonus-loaded deal is ~10% more appealing (lockout-proof,
    # immediate money). Scales linearly with the bonus share of AAV.
    try:
        _bonus_share = min(1.0, max(0.0, float(signing_bonus or 0)
                                    / max(1, float(aav or 1))))
        if _bonus_share > 0:
            parts["money"] = min(1.2, parts["money"]
                                 * (1.0 + 0.10 * _bonus_share))
            if _bonus_share >= 0.4:
                reasons.append(f"heavy signing-bonus money "
                               f"(${int(signing_bonus or 0):,} upfront)")
    except Exception:
        pass
    if ratio >= 1.25:
        reasons.append(f"a big overpay ({ratio:.0%} of market)")
    elif ratio <= 0.8:
        reasons.append(f"well below his market ({ratio:.0%})")

    # --- cup contention ----------------------------------------------------
    strength = _team_strength(team, league)
    parts["cup"] = strength
    if ambition == AMBITION_CUP:
        if strength >= 0.7:
            reasons.append(f"{_name(team)} can win it all right now")
        elif strength <= 0.35:
            reasons.append(f"{_name(team)} are years away -- a non-starter for a chaser")

    # --- ice time / role ---------------------------------------------------
    role, role_label = _projected_role(player, team)
    # kids crave opportunity even when their stated ambition is elsewhere
    kid_hunger = 0.25 if age <= 23 else 0.0
    parts["ice"] = max(role, kid_hunger + 0.5 * role)
    if ambition == AMBITION_ICE or age <= 23:
        reasons.append(f"he'd get {role_label} there")

    # --- staying vs leaving -------------------------------------------------
    if current_team is not None and current_team is team:
        tenure_f = min(1.0, _tenure(player, team) / 4.0)
        happy_f = 0.5 + 0.5 * (happiness / 100.0)
        parts["stay"] = min(1.0, 0.25 + 0.75 * (loyalty / 100.0)
                            * (0.4 + 0.6 * tenure_f) * happy_f)
        if loyalty >= 70:
            reasons.append("he's loyal -- it would take a lot to pry him away")
        if happiness < 40:
            reasons.append("he's unhappy where he is")
            parts["stay"] *= 0.5
    else:
        parts["stay"] = max(0.0, 0.5 - 0.5 * (loyalty / 100.0))
        if loyalty >= 75 and current_team is not None:
            reasons.append("leaving home would weigh on him")

    # --- hometown ------------------------------------------------------------
    home_pull, home_reason = _hometown_pull(player, team)
    parts["home"] = home_pull
    if home_reason:
        reasons.append(home_reason)

    # --- people in the room ----------------------------------------------------
    people, people_reasons = _people_pull(player, team)
    parts["people"] = max(0.0, min(1.0, 0.5 + people))
    reasons.extend(people_reasons)

    # --- weighted sum, then the bad-blood veto ---------------------------------
    appeal = sum(w[k] * parts.get(k, 0.5) for k in w)
    blood_cost, blood_reason = _rival_move_cost(player, current_team, team, app)
    if blood_reason:
        reasons.append(blood_reason)
    appeal -= blood_cost

    # Insult-offer guard (BUG-021): below ~2/3 of market, no room, role, or
    # hometown makes up the gap -- real players hang up. The veteran
    # cup-chase discount above is the one exemption (classic real case).
    _cup_discount = (ambition == AMBITION_CUP and age >= 32 and ratio < 1.0)
    if ratio < 0.65 and not _cup_discount:
        appeal *= 0.35
        reasons.append(f"an insult offer ({ratio:.0%} of market)")

    # L4 wire (Muck 2026-10-02): fanbase buzz. Players want to play
    # where the building is alive -- a buzzing fanbase is a real pull,
    # a toxic one a real repellent. Subtle (0.95-1.05), memory-aware: a
    # franchise with sustained buzz attracts; one the fans have turned
    # on repels. The reason strings ARE the story the player sees.
    try:
        from fan_narratives import fa_appeal_mult as _fam
        _buzz = float(_fam(team) or 1.0)
        if _buzz >= 1.03:
            appeal = min(1.0, appeal * _buzz)
            reasons.append("the building is electric -- he wants to play "
                           "in front of these fans")
        elif _buzz <= 0.97:
            appeal = max(0.0, appeal * _buzz)
            reasons.append("the fanbase has turned -- he'd rather play elsewhere")
    except Exception:
        pass

    # situation sanity: a cup-chaser won't sign with a rebuilder at any price
    # short of a ransom; a mercenary always has a price.
    if ambition == AMBITION_CUP and strength <= 0.3 and current_team is not team:
        appeal *= 0.7
    appeal = max(0.0, min(1.0, appeal))

    # keep the story tight: the 3 most decisive reasons
    return appeal, reasons[:3]


# ---------------------------------------------------------------------------
# Decision entry points
# ---------------------------------------------------------------------------

def player_accepts_offer_sheet(player, offering_team, aav: int, years: int,
                               original_team, league=None, app=None,
                               rng=None) -> Tuple[bool, float, List[str]]:
    """Would the RFA actually SIGN this offer sheet? The money is usually an
    overpay, but loyalty and bad blood are the classic vetoes."""
    r = rng or random.Random()
    appeal, reasons = contract_appeal(
        player, offering_team, aav, years, current_team=original_team,
        league=league, app=app, is_offer_sheet=True)
    # offer sheets are formal commitments: a soft yes isn't enough
    accepted = (appeal + r.uniform(-0.08, 0.08)) >= 0.52
    return accepted, appeal, reasons


def wants_out(player) -> bool:
    """Disgruntled enough to force his way out (the holdout path)."""
    ensure_decision_fields(player)
    happiness = float(getattr(player, "happiness", 70) or 70)
    loyalty = float(getattr(player, "loyalty", 50) or 50)
    return happiness < 32 and loyalty < 55


def ufa_accept_probability(player, team, salary_offer: int, years: int, *,
                           current_team=None, league=None, app=None) -> Tuple[float, List[str]]:
    """Drop-in for the FA negotiation roll: appeal -> acceptance chance."""
    appeal, reasons = contract_appeal(
        player, team, salary_offer, years, current_team=current_team,
        league=league, app=app)
    # map appeal to a probability with the same 0.05..0.95 rails the old
    # negotiation used, so behaviour stays sane at the extremes
    prob = 0.05 + 0.90 * appeal
    return prob, reasons
