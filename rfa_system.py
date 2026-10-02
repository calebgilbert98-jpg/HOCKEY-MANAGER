# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Restricted free agency, offer sheets, and salary arbitration — real NHL standard.

Real-life rules this module encodes (current CBA):

- RFA/UFA determination: a player whose contract expires is a restricted
  free agent unless he is 27+ on June 30 or has 7+ accrued pro seasons
  (Group 3 UFA). This is the same bar trade_engine.clause_eligible uses.
- Qualifying offers: the minimum tender a club must extend to retain an
  RFA's rights. Real CBA bands (QO_PCT_BY_SALARY below).
- Offer sheets: any club may sign another club's RFA to an offer sheet;
  the original club has 7 days to match. Compensation is a fixed table of
  draft picks by AAV band (OFFER_SHEET_COMPENSATION below), repriced each
  year against average league salary.
- Salary arbitration: Group 2 RFAs with enough pro experience may elect
  arbitration instead of negotiating; clubs may also elect it. The
  arbitrator picks from comparables and cannot go below 85% of the prior
  year's salary; clubs may walk away from player-elected awards above the
  walk-away threshold within 48 hours.

Occurrence realism: offer sheets and arbitration filings are rare in real
life. OFFER_SHEET_BASE_RATE and ARBITRATION_FILING_RATES are calibrated
to actual league counts over the past five seasons (see
docs/RFA_ARBITRATION_GUIDE.md), not to game convenience.

Design rules:
- Pure functions first (is_rfa, qualifying_offer_amount,
  offer_sheet_compensation, arbitration_eligible, arbitrator_award) so QA
  can assert real numbers without a GUI.
- process_rfa_offseason() is the single July entry point, called from
  main._start_offseason. It handles AI clubs end-to-end and queues the
  user's decisions as interactive inbox messages (action_type
  "rfa_decisions" / "offer_sheet_match"), never popups.
- Additive: never overrides calebgilbert98's cap/draft/rights systems.
  Rights retention rides on the existing draft-rights lifecycle; cap hits
  use the existing contract fields.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Real-life constants (verified 2026-09-28 vs the current CBA / 2020 MOU;
# sources in docs/RFA_ARBITRATION_GUIDE.md)
# ---------------------------------------------------------------------------

# Qualifying-offer minimums by prior-year Paragraph 1 base salary
# (CBA Article 10.2, 2020 MOU terms for 2025-26):
#   base < $775,000        -> 110%
#   $775,000..$999,999    -> 105%, capped at $1,000,000
#   base >= $1,000,000    -> lesser of prior salary or 120% of AAV
# (2026 CBA incoming: <=$1.25M -> 110%; $1.25M..$1.75M -> 105%;
#  >=$1.75M -> 100%. Flip QO_SCHEDULE_2026 when the sim gets there.)
QO_TIER1_MAX = 775_000
QO_TIER1_PCT = 1.10
QO_TIER2_MAX = 1_000_000
QO_TIER2_PCT = 1.05
QO_TIER2_CAP = 1_000_000
QO_TOP_AAV_MULT = 1.20


def qualifying_offer_pct(prior_salary: int) -> float:
    """Minimum qualifying-offer percentage for a prior-year base salary."""
    s = int(prior_salary or 0)
    if s < QO_TIER1_MAX:
        return QO_TIER1_PCT
    if s < QO_TIER2_MAX:
        return QO_TIER2_PCT
    return 1.00


def qualifying_offer_amount(prior_salary: int,
                            aav: Optional[int] = None) -> int:
    """Minimum qualifying-offer dollars (rounded to the nearest $1k).

    aav: the contract's average annual value. The game stores a single
    salary number as the cap hit (trade_engine._player_cap_hit), so aav
    defaults to prior_salary -- the 120%-of-AAV cap then only binds for
    back-loaded structures if a real AAV is ever tracked.
    """
    s = int(prior_salary or 0)
    a = int(aav if aav is not None else s)
    if s < QO_TIER1_MAX:
        amt = s * QO_TIER1_PCT
    elif s < QO_TIER2_MAX:
        amt = min(s * QO_TIER2_PCT, QO_TIER2_CAP)
    else:
        amt = min(s, QO_TOP_AAV_MULT * a)
    return int(round(amt / 1000.0) * 1000)


# Offer-sheet compensation (2025 offseason bands, re-indexed yearly to
# average league salary). (upper AAV bound inclusive, label, pick rounds --
# the signing club's OWN picks in the next draft.)
# AAV for compensation = total compensation / years; deals >5 years are
# divided by 5.
OFFER_SHEET_COMPENSATION: List[Tuple[int, str, List[int]]] = [
    (1_544_424, "No compensation", []),
    (2_340_037, "3rd-round pick", [3]),
    (4_680_076, "2nd-round pick", [2]),
    (7_020_113, "1st + 3rd-round picks", [1, 3]),
    (9_360_153, "1st + 2nd + 3rd-round picks", [1, 2, 3]),
    (11_700_192, "Two 1sts + 2nd + 3rd-round picks", [1, 1, 2, 3]),
    (10 ** 18, "Four 1st-round picks", [1, 1, 1, 1]),
]

# Walk-away: only from PLAYER-elected awards at/above this AAV, within
# 48 hours (then the player becomes a UFA). $4.85M for 2025-26.
ARBITRATION_WALK_AWAY_AAV = 4_850_000

# Arbitrator floor: award may not be less than 85% of prior-year salary.
ARBITRATION_FLOOR_PCT = 0.85

# Filing likelihood, calibrated to real filings 2021-2025 (mean ~19 per
# summer league-wide, range 13-26; ~95% settle pre-hearing). Per-eligible-
# RFA base rates, tier-weighted toward prominent players; the ask-gap
# multiplier concentrates filings where real disputes happen.
ARBITRATION_FILING_RATES = {
    "star": 0.40,
    "top6_top4": 0.24,
    "depth": 0.12,
}
# Share of filed cases that reach a hearing (~5% real: 5 awards in 94
# filings over five summers). The rest settle at ~midpoint of filings.
ARBITRATION_HEARING_RATE = 0.05

# Offer sheets: 12 in 20 cap-era years (~0.6/yr), 4 unmatched. Per
# (unsigned RFA, offering team) pair per summer, multiplied by target
# desirability. Calibrated: ~5 real targets x 31 clubs x 0.008 x ~0.5
# avg desirability ~= 0.6 sheets/year.
OFFER_SHEET_BASE_RATE = 0.008

# The original club has 7 days to match an offer sheet (CBA Article 10.3).
# If the clock runs out unanswered, the player goes to the offering club
# at the sheet terms -- the daily sweep enforces this, so no sheet can
# sit pending indefinitely.
OFFER_SHEET_MATCH_WINDOW_DAYS = 7

# Offer-sheet trade alternative (the sign-and-trade door): when the
# original club declines to match, a player/prospect package can replace
# the pick compensation when BOTH clubs prefer it --
#   * the original club takes the trade only if the package beats the
#     comp picks' trade value (a live player beats mystery picks);
#   * the offering club gives players instead of its picks only up to
#     GIVE_UP_MULT x the comp value.
# A user-involved club gets the choice (inbox message for the original
# club, dialog for the offering club); the choice window is stamped on
# the message and the daily sweep defaults an unanswered one to the
# picks, exactly as today. (TUNING: 1.0 / 1.25 / 3)
OFFER_SHEET_TRADE_ASK_MULT = 1.0
OFFER_SHEET_TRADE_GIVE_UP_MULT = 1.25
OFFER_SHEET_TRADE_WINDOW_DAYS = 3

# The jointly-appointed neutral panel (CBA: NHL + NHLPA appoint independent
# arbitrators yearly; cases assigned from the panel). Fictional names.
ARBITRATOR_PANEL = [
    "M. Ellison", "R. Beaumont", "S. Okafor", "D. Lindqvist",
    "J. Moreau", "T. Ashford", "K. Raman", "P. Novak",
]


# ---------------------------------------------------------------------------
# RFA / UFA determination
# ---------------------------------------------------------------------------

def _age(player) -> int:
    try:
        return int(getattr(player, "age", 0) or 0)
    except Exception:
        return 0


def _service_years(player) -> int:
    """Accrued pro seasons. Mirrors trade_engine.clause_eligible."""
    try:
        return int(getattr(player, "seasons_played", 0) or 0)
    except Exception:
        return 0


def contract_expired(player) -> bool:
    c = getattr(player, "contract", None)
    return bool(c is not None and int(getattr(c, "years_remaining", 0) or 0) <= 0)


def _is_goalie(player) -> bool:
    pos = getattr(getattr(player, "primary_position", None), "value", None)
    return str(pos or "") == "G"


def is_group6_ufa(player) -> bool:
    """Group 6 carve-out: age 25+, 3+ pro seasons, but <80 NHL GP
    (skaters) / <28 NHL GP (goalies) -> UFA, not RFA."""
    if _age(player) < 25 or _service_years(player) < 3:
        return False
    if _is_goalie(player):
        return int(getattr(player, "career_games_goalie", 0) or 0) < 28
    return int(getattr(player, "career_games", 0) or 0) < 80


def is_ufa_eligible(player) -> bool:
    """UFA bar: 27+ on June 30 or 7+ accrued seasons (Group 3), or the
    Group 6 carve-out (25+/3+ pro seasons but barely any NHL games)."""
    return (_age(player) >= 27 or _service_years(player) >= 7
            or is_group6_ufa(player))


def is_rfa(player) -> bool:
    """An expired-contract player who is NOT UFA-eligible is an RFA."""
    return contract_expired(player) and not is_ufa_eligible(player)


def is_ufa(player) -> bool:
    """An expired-contract player who IS UFA-eligible is a UFA."""
    return contract_expired(player) and is_ufa_eligible(player)


def rfa_rights_at_impasse(player) -> bool:
    """True when an unsigned RFA's rights are shoppable at a risk discount.

    A genuine signing impasse: the club holds his rights (he was
    qualified) but he won't sign -- he wants out (the holdout path in
    process_rfa_offseason: he refuses the QO and holds out into the
    offer-sheet pool) or the relationship is in arbitration (a formal
    valuation dispute). A player with a live offer-sheet decision
    pending is excluded -- his rights aren't shoppable mid-decision.
    Plain unsigned RFAs still in normal July talks are NOT at an
    impasse. Used by trade_engine.player_trade_value as one additive
    risk adjustment; the base weights are never retuned here.
    """
    try:
        if not is_rfa(player):
            return False
        if not bool(getattr(player, "qo_extended", False)):
            return False  # unqualified: the club holds no rights
        if bool(getattr(player, "offer_sheet_pending", False)):
            return False
        if bool(getattr(player, "arbitration_filed", False)):
            return True
        try:
            import player_decision as _pd
            if _pd.wants_out(player):
                return True
        except Exception:
            pass
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Offer-sheet compensation
# ---------------------------------------------------------------------------

def offer_sheet_compensation(aav: int) -> Tuple[str, List[int]]:
    """(label, picks) for an offer sheet at the given AAV.

    Returns ([], "No compensation") below the first band.
    """
    a = int(aav or 0)
    for upper, label, picks in OFFER_SHEET_COMPENSATION:
        if a <= upper:
            return label, list(picks)
    # Above the top band: the maximum compensation.
    if OFFER_SHEET_COMPENSATION:
        label, picks = OFFER_SHEET_COMPENSATION[-1][1], OFFER_SHEET_COMPENSATION[-1][2]
        return label, list(picks)
    return "No compensation", []


# ---------------------------------------------------------------------------
# Arbitration
# ---------------------------------------------------------------------------

# Arbitration experience thresholds (CBA Article 12): required pro years
# by the player's age on Sept 15 of the year he signed his first SPC.
_ARBITRATION_EXPERIENCE = (
    ((18, 19, 20), 4),
    ((21,), 3),
    ((22, 23), 2),
)


def _estimated_signing_age(player) -> int:
    """Age at first SPC signing. The game doesn't stamp signing age, so we
    estimate it as current age minus accrued pro seasons (players turn pro
    continuously) — documented approximation, good enough for the gate."""
    try:
        return max(18, _age(player) - _service_years(player))
    except Exception:
        return 24


def arbitration_eligible(player) -> bool:
    """Group 2 RFA with enough pro experience (CBA Article 12).

    Required pro years by age at first SPC signing: 18-20 -> 4; 21 -> 3;
    22-23 -> 2; 24+ -> 1. Must also not have signed an offer sheet.
    """
    if not is_rfa(player):
        return False
    if bool(getattr(player, "offer_sheet_pending", False)):
        return False
    signing_age = _estimated_signing_age(player)
    required = 1
    for ages, yrs in _ARBITRATION_EXPERIENCE:
        if signing_age in ages:
            required = yrs
            break
    return _service_years(player) >= required


def _player_tier(player) -> str:
    """star / top6_top4 / depth — drives filing likelihood."""
    try:
        ovr = float(player.overall_rating())
    except Exception:
        ovr = 75.0
    if ovr >= 86:
        return "star"
    if ovr >= 80:
        return "top6_top4"
    return "depth"


def arbitration_filing_probability(player, context: Optional[dict] = None) -> float:
    """Real-life-calibrated probability this RFA files for arbitration.

    Only called when the player is arbitration-eligible and unsigned past
    the election window — i.e. exactly the real-life circumstances.
    """
    if not arbitration_eligible(player):
        return 0.0
    tier = _player_tier(player)
    base = float(ARBITRATION_FILING_RATES.get(tier, 0.0))
    # Big gap between ask and team offer makes filing more likely, as in
    # real life (filings cluster around genuine valuation disputes).
    ctx = context or {}
    try:
        gap = float(ctx.get("ask_gap_pct", 0.0) or 0.0)
    except Exception:
        gap = 0.0
    return min(0.95, base * (1.0 + max(0.0, gap) * 2.0))


def _ufa_in_years(player) -> int:
    """Years until Group 3 UFA eligibility (27 or 7 accrued seasons)."""
    yrs_age = max(0, 27 - _age(player))
    yrs_svc = max(0, 7 - _service_years(player))
    return min(yrs_age, yrs_svc)


def arbitrator_award(player, player_ask: int, team_offer: int,
                     comparables: Optional[List[int]] = None,
                     rng: Optional[random.Random] = None,
                     filed_by: str = "player") -> Dict[str, Any]:
    """League-standard arbitrator decision.

    Real process: the arbitrator hears both figures, weighs comparable
    contracts (players of similar role/age/production), and issues a 1- or
    2-year award. The award may not fall below 85% of the prior salary.
    This models the award as a comparables-anchored pick inside the
    [floor, max(ask, comparables)] range — the arbitrator "splits" toward
    the comparables, as real awards do.
    """
    r = rng or random.Random()
    prior = int(getattr(getattr(player, "contract", None), "salary", 0) or 0)
    floor = int(prior * ARBITRATION_FLOOR_PCT)
    ask = int(player_ask or 0)
    offer = int(team_offer or 0)
    comps = [int(c) for c in (comparables or []) if c and c > 0]
    anchor = int(sum(comps) / len(comps)) if comps else (ask + offer) // 2
    # The arbitrator lands between the midpoint of the two filings and the
    # comparables anchor, never below the floor, never above the ask.
    midpoint = (ask + offer) // 2
    target = (midpoint + anchor) // 2
    award = max(floor, min(ask, target))
    # Small realistic variance: arbitrators round to human numbers.
    award = int(round(award / 25000.0) * 25000)
    award = max(floor, award)
    # Term: player-elected -> the team chooses 1 vs 2 years after the AAV
    # is set. Teams take the 2nd year when it buys a cheap RFA year, but a
    # 2-year award may not walk the player straight into UFA eligibility.
    if _ufa_in_years(player) <= 2:
        term = 1
    elif filed_by == "player":
        term = 2 if award < _market_value(player) * 1.1 else 1
    else:
        term = 1 if r.random() < 0.7 else 2
    # Walk-away exists ONLY for player-elected awards at/above the
    # threshold ($4.85M, 2025-26) -- never for club-elected awards.
    walk_away_available = (filed_by == "player"
                           and award >= ARBITRATION_WALK_AWAY_AAV)
    arbitrator = r.choice(ARBITRATOR_PANEL)
    return {
        "award_aav": award,
        "term_years": term,
        "floor": floor,
        "walk_away_available": walk_away_available,
        "comparables_used": len(comps),
        "arbitrator": arbitrator,
        "filed_by": filed_by,
    }


def settle_arbitration(player_ask: int, team_offer: int,
                       rng: Optional[random.Random] = None) -> Dict[str, Any]:
    """Pre-hearing settlement (~95% of real filings).

    Settles at the midpoint of the two filings with a slight player lean
    (Robertson 2025: asked $2.25M vs $1.2M -> settled $1.825M, just above
    the $1.725M midpoint). Term 1-3 years; real settlements skew multi-year.
    """
    r = rng or random.Random()
    midpoint = (int(player_ask or 0) + int(team_offer or 0)) // 2
    # Slight player lean: up to +4% above midpoint.
    aav = int(midpoint * (1.0 + r.random() * 0.04))
    aav = int(round(aav / 25000.0) * 25000)
    term = 1 if r.random() < 0.25 else (2 if r.random() < 0.6 else 3)
    return {"award_aav": aav, "term_years": term, "settled": True}


# ---------------------------------------------------------------------------
# July offseason pass
# ---------------------------------------------------------------------------

def _team_name(team) -> str:
    for attr in ("team_name", "name", "city"):
        v = getattr(team, attr, None)
        if v:
            return str(v)
    return "Unknown"


def _is_user_team(team) -> bool:
    try:
        from game_classes import is_human_managed
        return bool(is_human_managed(team))
    except Exception:
        return bool(getattr(team, "is_user_team", False))


def _market_value(player) -> int:
    """Best-effort market AAV using the game's own estimator when present."""
    try:
        from windows import ContractNegotiationView
        v = ContractNegotiationView._estimate_market_value(player)
        return int(v or 0)
    except Exception:
        pass
    try:
        ovr = float(player.overall_rating())
    except Exception:
        ovr = 75.0
    return int(max(750_000, (ovr - 60) * 250_000))


def _sign_player(team, player, aav: int, years: int) -> bool:
    # R1 (roster limits): Dec-1 ineligible RFAs can't sign anywhere, and
    # emergency fill-ins can't take standard deals. Refuse (False), don't
    # corrupt -- fail-safe: every caller ignores the return value.
    try:
        import roster_limits as _rl
        _ok, _why = _rl.can_sign_player(player)
        if not _ok:
            return False
    except Exception:
        pass
    c = getattr(player, "contract", None)
    if c is not None:
        c.salary = int(aav)
        c.years_remaining = int(years)
    try:
        player.contract_years = int(years)
    except Exception:
        pass
    for attr in ("qo_extended", "arbitration_filed", "offer_sheet_pending"):
        try:
            setattr(player, attr, False)
        except Exception:
            pass
    return True


def _register_market_signing(league, player, aav: int) -> None:
    """Register a signed deal with the cap market engine (Caleb's
    register_signing), so offer-sheet signings -- matched or not -- move
    future comparable asks exactly like every other signing. Additive
    wrapper; the salary-cap system itself is untouched."""
    try:
        _cap_sys = getattr(league, "salary_cap_system", None)
        if _cap_sys is None:
            return
        pname = getattr(player, "full_name", getattr(player, "name",
                                                     "Unknown"))
        try:
            from game_classes import to_100_scale as _t100
            _ovr100 = int(_t100(player.overall_rating()))
        except Exception:
            try:
                _ovr100 = int(player.overall_rating() * 2)
            except Exception:
                _ovr100 = 75
        _pos = getattr(player, "primary_position", "")
        _pos_name = _pos.value if hasattr(_pos, "value") else str(_pos)
        _cap_sys.register_signing(
            pname, int(aav), _ovr100, _pos_name,
            int(getattr(player, "age", 27) or 27),
            int(getattr(league, "season_year", 0) or 0))
    except Exception:
        pass


def apply_offer_sheet_matched(league, offering_team, original_team, player,
                              aav: int, years: int,
                              app=None) -> Dict[str, Any]:
    """The original club matched: the player signs WITH THE ORIGINAL CLUB
    at the offer-sheet terms (real NHL rule) -- same outcome no matter
    which match path got here (July AI pass, user inbox decision, or the
    user's own sheet matched by an AI club).

    Signs at the sheet terms, registers cap so the market engine learns,
    sets the 1-year no-trade-without-consent flag, and records the sheet's
    heat (the sheet was signed -- the rivalry fallout exists either way).
    The player does not move and no picks change hands on a match.
    """
    _sign_player(original_team, player, aav, years)
    try:
        player.offer_sheet_match_no_trade_until = int(
            getattr(league, "season_year", 2026) or 2026) + 1
    except Exception:
        pass
    _register_market_signing(league, player, aav)
    try:
        import reputation_system as _rep
        _rep.record_offer_sheet(
            getattr(league, "rivalries", []), offering_team, original_team,
            player, aav)
    except Exception:
        pass
    pname = getattr(player, "full_name", getattr(player, "name", "Unknown"))
    story = (f"\u270d\ufe0f OFFER SHEET: {_team_name(offering_team)} "
             f"sign {pname} (${aav:,}/yr \u00d7 {years}y) -- "
             f"{_team_name(original_team)} match and keep him.")
    if app is not None:
        try:
            app.add_news(story)
        except Exception:
            pass
    return {"ok": True, "matched": True, "story": story}


def _move_to_free_agents(league, player) -> None:
    for team in getattr(league, "teams", []) or []:
        roster = getattr(team, "roster", None)
        if roster is not None and player in roster:
            try:
                player.last_team_name = _team_name(team)
            except Exception:
                pass
            try:
                roster.remove(player)
            except Exception:
                pass
    pool = getattr(league, "free_agents", None)
    if pool is not None and player not in pool:
        pool.append(player)


def _ai_qualify_decision(team, player, qo_amount: int) -> bool:
    """Would an AI club extend the qualifying offer? Real clubs qualify
    anyone who is a plausible NHL contributor and non-tender fringe/
    replacement-level RFAs (who then become UFAs)."""
    try:
        ovr = float(player.overall_rating())
    except Exception:
        ovr = 70.0
    age = _age(player)
    core = _is_core_keep(player)
    contributor = core or (age <= 24 and ovr >= 74) or ovr >= 77 or ovr >= 72
    if not contributor:
        return False  # fringe: non-tender, he walks
    # Cap-conscious: stars are worth dipping into the reserve for;
    # everyone else must fit inside the plan (reserve + roster math).
    return qo_amount <= _spending_budget(team, core=core)


def _scarcity_mult(league, player) -> float:
    """UFA/RFA scarcity multiplier for one player (1.0 when unknown).

    One market for user and AI: re-sign asks and offer sheets ride the
    same supply/demand read the negotiation paths use."""
    try:
        from salary_cap_system import fa_market_scarcity as _fms
        pos = getattr(getattr(player, "primary_position", ""),
                      "value", "") or ""
        return float(_fms(league, pos).get("multiplier", 1.0))
    except Exception:
        return 1.0


def _ai_rfa_deal(player, qo_amount: int, rng, league=None) -> Tuple[int, int]:
    """AI club re-signs its qualified RFA: most sign near the QO or a
    short market deal; bridge deals for the young and good.

    Market-based outcomes carry the scarcity read (same market the user
    negotiates in); the bare QO outcome is a fixed CBA floor and is not
    scarcity-adjusted."""
    market = int(_market_value(player) * _scarcity_mult(league, player))
    age = _age(player)
    try:
        ovr = float(player.overall_rating())
    except Exception:
        ovr = 76.0
    if age <= 24 and ovr >= 80 and rng.random() < 0.5:
        return int(market * 1.05), rng.choice([2, 3])
    if rng.random() < 0.55:
        return qo_amount, 1
    aav = int(min(market, qo_amount * 1.6))
    return max(qo_amount, aav), rng.choice([1, 2])


def process_rfa_offseason(league, app=None, rng=None) -> Dict[str, Any]:
    """July entry point: qualifying offers, offer sheets, arbitration.

    AI clubs are processed end-to-end. The user's RFAs are queued as an
    interactive inbox message (action_type "rfa_qualifying"); unsigned
    user RFAs that draw offer sheets arrive as "offer_sheet_match"
    messages. Returns a summary dict for the offseason report.
    """
    r = rng or random.Random()
    # The pass models July mechanics while the stamped game date is still
    # late June: offer sheets are judged on July 1 of the new league year.
    from datetime import date as _date
    try:
        _july_year = int(getattr(league, "season_year", 2026) or 2026) + 1
    except Exception:
        _july_year = 2027
    summary: Dict[str, Any] = {
        "rfas": 0, "ufas": 0, "qualified": 0, "non_tendered": 0,
        "offer_sheets": 0, "arbitration_filings": 0, "arbitration_awards": [],
        "user_rfas": [],
    }
    user_team = None
    ai_teams = []
    for team in getattr(league, "teams", []) or []:
        if _is_user_team(team):
            user_team = team
        else:
            ai_teams.append(team)

    # --- 0. New league year: last season's Dec-1 ineligibility is spent.
    # A qualified-but-unsigned RFA who sat out past Dec 1 re-enters the
    # QO flow below like any other unsigned RFA (true NHL: the club still
    # holds his rights). Without this he would be unsignable forever.
    for team in list(getattr(league, "teams", []) or []):
        for player in list(getattr(team, "roster", []) or []):
            try:
                if getattr(player, "season_ineligible", False):
                    player.season_ineligible = False
            except Exception:
                continue

    # --- 1. Classify every expired contract --------------------------------
    for team in list(getattr(league, "teams", []) or []):
        for player in list(getattr(team, "roster", []) or []):
            if not contract_expired(player):
                continue
            if is_rfa(player):
                summary["rfas"] += 1
            elif is_ufa(player):
                summary["ufas"] += 1

    # --- 2. AI clubs: qualifying offers ------------------------------------
    unsigned_rfas: List[Tuple[Any, Any, int]] = []
    for team in ai_teams:
        for player in list(getattr(team, "roster", []) or []):
            if not is_rfa(player):
                continue
            prior = int(getattr(getattr(player, "contract", None),
                                "salary", 0) or 0)
            qo = qualifying_offer_amount(prior)
            if _ai_qualify_decision(team, player, qo):
                try:
                    player.qo_extended = True
                    player.qo_amount = qo
                except Exception:
                    pass
                summary["qualified"] += 1
                unsigned_rfas.append((team, player, qo))
            else:
                summary["non_tendered"] += 1
                _move_to_free_agents(league, player)

    # --- 3. AI clubs: re-sign their qualified RFAs --------------------------
    # ~40% sign before July; the rest negotiate into July unsigned -- the
    # offer-sheet and arbitration pool, as in real life (filings: July 5).
    still_unsigned: List[Tuple[Any, Any, int]] = []
    for team, player, qo in unsigned_rfas:
        if r.random() < 0.60:
            still_unsigned.append((team, player, qo))
            continue
        try:
            import player_decision as _pd
            if _pd.wants_out(player):
                # He wants out and won't sign the QO: he holds out into the
                # offer-sheet/arbitration pool (the Tkachuk path) rather than
                # re-signing somewhere he's miserable.
                still_unsigned.append((team, player, qo))
                continue
        except Exception:
            pass
        budget = _spending_budget(team, core=_is_core_keep(player))
        if budget < LEAGUE_MIN_SALARY:
            # Doesn't fit the plan: he holds out (stays unsigned) rather
            # than the club wrecking its cap structure.
            still_unsigned.append((team, player, qo))
            continue
        aav, years = _ai_rfa_deal(player, qo, r, league=league)
        _sign_player(team, player, min(aav, int(budget)), years)

    # --- 4. AI clubs: UFAs — re-sign the core, release the rest -------------
    for team in ai_teams:
        for player in list(getattr(team, "roster", []) or []):
            if not is_ufa(player):
                continue
            try:
                ovr = float(player.overall_rating())
            except Exception:
                ovr = 70.0
            tenure = _service_years(player)
            if ovr >= 82 or (ovr >= 78 and tenure >= 5):
                market = int(_market_value(player)
                             * _scarcity_mult(league, player))
                budget = _spending_budget(team, core=True)
                if market <= budget:
                    _sign_player(team, player, market,
                                 r.choice([2, 3, 4] if ovr >= 84 else [1, 2]))
                elif budget >= LEAGUE_MIN_SALARY:
                    # Cap-strapped: 1-year prove-it deal at what the plan
                    # allows -- never at the cost of icing a roster.
                    _sign_player(team, player, int(budget), 1)
                # else: doesn't fit the plan -- falls through to the pool
            else:
                _move_to_free_agents(league, player)

    # --- 4b. AI backfill: released UFAs leave holes; fill from within -----
    # Promote signed prospects first (the real pipeline), then cheap UFAs
    # from the pool. Without this, AI rosters would shrink every summer
    # (previously expired deals just sat "Unsigned" on the roster).
    for team in ai_teams:
        _ai_backfill_roster(team, league, r)

    # --- 5. Offer sheets: rare, deliberate, real-life-shaped ----------------
    # Targets: unsigned RFAs who have not filed for arbitration (filing
    # blocks offer sheets) and have not accepted a QO. ~0.6/yr league-wide
    # in real life (12 in 20 cap-era years).
    # NOTE: the user's RFAs are NOT touched here. When the user extends
    # a QO via the inbox, resolve_user_rfa() runs the same July mechanics
    # for that player (offer-sheet risk, arbitration filing) -- no
    # provisional states, nothing to void.
    offer_sheet_targets: List[Tuple[Any, Any, int]] = list(still_unsigned)
    for original_team, player, qo in offer_sheet_targets:
        if bool(getattr(player, "arbitration_filed", False)):
            continue
        for offering_team in getattr(league, "teams", []) or []:
            if offering_team is original_team:
                continue
            if _is_user_team(offering_team):
                continue  # the user signs offer sheets via the UI, not here
            market = _market_value(player)
            # Scarcity rides along: poaching a scarce position costs the
            # same premium the open market would demand.
            aav = int(market * (1.05 + r.random() * 0.25)
                      * _scarcity_mult(league, player))
            score = ai_offer_sheet_target_score(offering_team, player, aav)
            if score <= 0:
                continue
            if r.random() > OFFER_SHEET_BASE_RATE * score:
                continue
            years = r.choice([1, 2, 3, 4, 5])
            label, picks = offer_sheet_compensation(aav)
            # --- the PLAYER's side: he must agree to sign the sheet --------
            # Loyalty and bad blood are the classic vetoes (nobody signs
            # with a hated rival lightly -- especially a fan favourite who
            # would turn the love into boos overnight).
            try:
                import player_decision as _pd
                _willing, _appeal, _why = _pd.player_accepts_offer_sheet(
                    player, offering_team, aav, years, original_team,
                    league=league, app=app, rng=r)
            except Exception:
                _willing, _why = True, []
            if not _willing:
                continue  # he won't sign there; next suitor
            if ai_match_decision(original_team, player, aav, label):
                # Matched: he signs WITH THE ORIGINAL CLUB at the sheet
                # terms (real NHL rule) -- cap registered, no-trade flag
                # set. Same helper every match path uses.
                apply_offer_sheet_matched(league, offering_team,
                                          original_team, player, aav, years,
                                          app=app)
            else:
                res = execute_offer_sheet(league, offering_team,
                                          original_team, player, aav, years,
                                          app=app, rng=r,
                                          as_of=_date(_july_year, 7, 1))
                if res.get("ok"):
                    summary["offer_sheets"] += 1
            break  # one suitor per RFA per summer

    # --- 6. Arbitration: filings at real-life-calibrated rates ---------------
    # Player-elected only here; club-elected is handled as a rare event
    # below (0-2 per summer league-wide, real shape).
    for original_team, player, qo in offer_sheet_targets:
        if not arbitration_eligible(player):
            continue
        if contract_expired(player) is False:
            continue  # signed since (matched sheet, ...)
        ask_gap = 0.25  # AI numbers: genuine valuation dispute assumed
        prob = arbitration_filing_probability(
            player, {"ask_gap_pct": ask_gap})
        if r.random() > prob:
            continue
        try:
            player.arbitration_filed = True
        except Exception:
            pass
        summary["arbitration_filings"] += 1
        res = resolve_arbitration(league, original_team, player,
                                  filed_by="player", app=app, rng=r)
        summary["arbitration_awards"].append(res.get("story", ""))
    # Rare club-elected cases (0-2 per summer league-wide).
    _club_elected_arbitration(league, ai_teams, app, r, summary)

    # --- 6b. July signings: unsigned AI RFAs who filed nothing sign -------
    for original_team, player, qo in offer_sheet_targets:
        if contract_expired(player) is False:
            continue
        if bool(getattr(player, "arbitration_filed", False)):
            continue
        budget = _spending_budget(original_team,
                                    core=_is_core_keep(player))
        if budget < LEAGUE_MIN_SALARY:
            continue  # still doesn't fit the plan: the holdout continues
        aav, years = _ai_rfa_deal(player, qo, r, league=league)
        _sign_player(original_team, player, min(aav, int(budget)), years)
        summary["qualified"] += 0  # counted at qualify time

    # --- 6c. Cap-compliance sweep: the guarantee -------------------------
    # Every AI spend path above is hard-capped, but dead-cap subtleties
    # (buyouts landing post-generation, retained salary) can still tip a
    # borderline roster over. Real clubs paper players down on these days;
    # demote (two-ways first: fully exempt) until compliant. AI teams never
    # enter the season over the cap, so no unsolvable states exist.
    for team in ai_teams:
        _ai_cap_compliance_sweep(team)

    # --- 6d. July 1: unsigned UFAs leave (R1, true NHL) -------------------
    # Expired UFA deals come off the roster AND off the cap -- for the user
    # team too. This is the structural fix for Sim A's $31.36M phantom
    # overage (nothing ever moved expired deals). RFAs are untouched:
    # rights retained, the QO flow owns them. Emergency fillers never
    # carry over the summer either.
    try:
        import roster_limits as _rl
        for team in list(getattr(league, "teams", None) or []):
            try:
                _rl.release_all_fillers(team)
            except Exception:
                continue
        _rl.july_release_unsigned_ufas(league, app)
    except Exception:
        pass

    # --- 6e. Roster-compliance sweep (R1): the same guarantee for the
    # 23-man max and the dressed minimum. Runs AFTER the July releases so
    # the sweep's fillers survive: no AI club leaves July unable to dress
    # 18+2 -- short clubs get emergency fill-ins via the same backstop
    # the daily AI tick uses.
    try:
        import roster_limits as _rl2
        for team in ai_teams:
            try:
                _rl2.ai_roster_compliance(team, league, r)
            except Exception:
                continue
    except Exception:
        pass

    # --- 7. User team: queue qualifying decisions ----------------------------
    if user_team is not None and app is not None:
        cards = []
        for player in list(getattr(user_team, "roster", []) or []):
            if not is_rfa(player):
                continue
            prior = int(getattr(getattr(player, "contract", None),
                                "salary", 0) or 0)
            qo = qualifying_offer_amount(prior)
            cards.append({
                "player_id": getattr(player, "id", None),
                "name": getattr(player, "full_name",
                                getattr(player, "name", "Unknown")),
                "prior_salary": prior,
                "qo_amount": qo,
                "age": _age(player),
            })
            summary["user_rfas"].append(getattr(player, "full_name",
                                               getattr(player, "name", "?")))
        if cards:
            _queue_rfa_decisions(app, user_team, cards)

    return summary


def tname(team) -> str:
    return _team_name(team)


def _club_elected_arbitration(league, ai_teams, app, r, summary) -> None:
    """0-2 club-elected cases per summer (real: Byram/McBain 2025). Only on
    qualified RFAs the club wants to keep at a controlled number."""
    n = 1 if r.random() < 0.35 else (2 if r.random() < 0.08 else 0)
    if n == 0:
        return
    candidates = []
    for team in ai_teams:
        for player in list(getattr(team, "roster", []) or []):
            if not arbitration_eligible(player):
                continue
            if not contract_expired(player):
                continue
            if bool(getattr(player, "arbitration_filed", False)):
                continue
            if bool(getattr(player, "club_arbitrated_before", False)):
                continue  # once per career
            try:
                ovr = float(player.overall_rating())
            except Exception:
                ovr = 75.0
            if 78 <= ovr <= 84:
                candidates.append((team, player))
    r.shuffle(candidates)
    for team, player in candidates[:n]:
        try:
            player.club_arbitrated_before = True
            player.arbitration_filed = True
        except Exception:
            pass
        summary["arbitration_filings"] += 1
        res = resolve_arbitration(league, team, player, filed_by="club",
                                  app=app, rng=r)
        summary["arbitration_awards"].append(res.get("story", ""))


def _queue_offer_sheet_match(app, league, offering_team, original_team,
                             player, aav: int, years: int,
                             compensation_label: str,
                             player_reasons: Optional[List[str]] = None) -> None:
    """Interactive inbox message: match the offer sheet or take the picks
    (7-day clock, as in real life). Stamps the real match deadline into
    the message's action_data; if the user lets the clock run out, the
    daily sweep (process_offer_sheet_deadlines) resolves it as a decline
    -- the player goes to the offering club at the sheet terms, exactly
    the real CBA rule."""
    if app is None:
        return
    try:
        from game_classes import EmailMessage
    except Exception:
        return
    pname = getattr(player, "full_name", getattr(player, "name", "Unknown"))
    intel = ""
    try:
        if player_reasons:
            intel = (f"\n\nWord from {pname.split()[-1]}'s camp: "
                     f"{player_reasons[0]}.")
    except Exception:
        intel = ""
    # The sheet is live from the moment the offering club signs it: mark
    # the player pending (blocks a second sheet and arbitration while the
    # decision is open -- real life treats the signed sheet as binding).
    try:
        player.offer_sheet_pending = True
    except Exception:
        pass
    try:
        from datetime import timedelta as _td
        _today = getattr(app, "current_date", None)
        if _today is not None and hasattr(_today, "isoformat"):
            _deadline = _today + _td(days=OFFER_SHEET_MATCH_WINDOW_DAYS)
            _deadline_iso = _deadline.isoformat()
            _deadline_txt = _deadline.strftime("%b %d, %Y")
        else:
            _deadline_iso, _deadline_txt = None, "7 days from today"
    except Exception:
        _deadline_iso, _deadline_txt = None, "7 days from today"
    msg = EmailMessage(
        sender=_team_name(offering_team),
        sender_type="System",
        subject=f"Offer sheet: {pname} — match or take picks?",
        content=(f"{_team_name(offering_team)} have signed your RFA {pname} "
                 f"to an offer sheet: ${_format_money(aav)}/yr x {years}y.\n\n"
                 f"Match it and keep him at those terms (he can't be traded "
                 f"for a year without his consent), or decline and take the "
                 f"compensation: {compensation_label}.\n\n"
                 f"You have until {_deadline_txt} to decide -- if the clock "
                 f"runs out he walks for the picks.{intel}"),
        category="Contracts",
        is_important=True,
        is_urgent=True,
        requires_response=True,
        game_date_sent=getattr(app, "current_date", None),
        action_type="offer_sheet_match",
        action_data={
            "player_id": getattr(player, "id", None),
            "offering_team_id": getattr(offering_team, "id", None),
            "original_team_id": getattr(original_team, "id", None),
            "aav": aav,
            "years": years,
            "compensation": compensation_label,
            "match_deadline": _deadline_iso,
            # Teams carry no id field: the name is the stable identity
            # (the id keys are kept for forward compatibility only).
            "offering_team_name": _team_name(offering_team),
            "original_team_name": _team_name(original_team),
        },
    )
    try:
        app.send_email_to_user(msg)
    except Exception:
        pass


def _queue_rfa_decisions(app, team, cards: List[dict]) -> None:
    """Interactive inbox message: qualify or non-tender each RFA."""
    try:
        from game_classes import EmailMessage
    except Exception:
        return
    room = _cap_room(team)
    total_qo = sum(int(c.get("qo_amount", 0) or 0) for c in cards)
    lines = ["Your restricted free agents need qualifying offers by the "
             "deadline. Extend the QO to keep their rights, or decline and "
             "let them walk as UFAs:",
             f"Cap space: {_format_money(room)} — qualifying everyone costs "
             f"{_format_money(total_qo)}."]
    if total_qo > room:
        lines.append("WARNING: qualifying everyone puts you over the cap. "
                     "You can still do it, but you won't be able to advance "
                     "the day until you shed salary (trade, waivers, "
                     "demotion).")
    for c in cards:
        lines.append(f"• {c['name']} (age {c['age']}): "
                     f"QO {_format_money(c['qo_amount'])} "
                     f"(was {_format_money(c['prior_salary'])})")
    msg = EmailMessage(
        sender="League Office",
        sender_type="System",
        subject=f"Qualifying offers due — {len(cards)} restricted free agents",
        content="\n".join(lines),
        category="Contracts",
        is_important=True,
        requires_response=True,
        action_type="rfa_qualifying",
        action_data={"cards": cards,
                     "team_id": getattr(team, "id", None),
                     "cap_space": int(room)},
    )
    try:
        app.send_email_to_user(msg)
    except Exception:
        pass


def _format_money(n) -> str:
    try:
        return f"${int(n):,}"
    except Exception:
        return "$0"

# ---------------------------------------------------------------------------
# Offer sheets — execution
# ---------------------------------------------------------------------------

def _own_pick(team, year: int, round_no: int):
    """The team's own untraded pick for (year, round), or None."""
    team_names = {str(getattr(team, "team_name", "") or ""),
                  str(getattr(team, "name", "") or "")}
    for picks in (getattr(team, "draft_picks", {}) or {}).get(year, []) or []:
        if int(getattr(picks, "round", 0) or 0) != int(round_no):
            continue
        orig = str(getattr(picks, "original_team", "") or "")
        cur = str(getattr(picks, "current_team", "") or "")
        if orig in team_names and cur in team_names:
            return picks
    return None


def _transfer_pick(pick, from_team, to_team) -> None:
    to_names = {str(getattr(to_team, "team_name", "") or ""),
                str(getattr(to_team, "name", "") or "")}
    to_name = str(getattr(to_team, "team_name", None)
                  or getattr(to_team, "name", "") or "")
    try:
        pick.current_team = to_name
        # Remove from giver's pool, add to receiver's pool.
        for yr, pool in (getattr(from_team, "draft_picks", {}) or {}).items():
            if pick in pool:
                pool.remove(pick)
        # NB: (getattr(...) or {}) would build a throwaway dict when the
        # receiver's pool map is empty -- the pick would silently vanish.
        pools = getattr(to_team, "draft_picks", None)
        if not isinstance(pools, dict):
            pools = {}
            try:
                to_team.draft_picks = pools
            except Exception:
                pass
        pool = pools.setdefault(getattr(pick, "year", 0), [])
        if pick not in pool:
            pool.append(pick)
    except Exception:
        pass
    _ = to_names


# ---------------------------------------------------------------------------
# Public helpers for the offer-sheet UI (offer_sheet_ui.py)
# ---------------------------------------------------------------------------

def own_pick_available(team, year: int, round_no: int):
    """Public wrapper: the team's own untraded pick for (year, round)."""
    return _own_pick(team, year, int(round_no))


def market_value_estimate(player) -> int:
    """Public wrapper: the engine's market read for an RFA (UI display)."""
    try:
        return int(_market_value(player) or 0)
    except Exception:
        return 0



def execute_offer_sheet(league, offering_team, original_team, player,
                        aav: int, years: int, app=None, rng=None,
                        as_of=None, expired=False,
                        _skip_trade_alt=False) -> Dict[str, Any]:
    """Sign an unsigned RFA to an offer sheet.

    Moves the player, transfers the real compensation picks, feeds the
    existing reputation hooks (record_offer_sheet), and posts league news.
    Matching is the caller's decision — call this only for the signed
    outcome (matched = player stays; unmatched = this runs).

    as_of: the date the window is judged on. The July RFA pass runs while
    the stamped game date is still late June, so it passes July 1
    explicitly (the pass models July mechanics).

    expired: True when the 7-day match clock already ran out (the daily
    sweep path). An expired decline goes straight to the compensation --
    the club already forfeited its decision window, so no trade
    alternative is offered.

    _skip_trade_alt: internal. The trade-alternative fallback paths set
    this so a declined/expired trade choice runs the compensation
    exactly as today without re-triggering the hook.
    """
    # Offer-sheet window (real NHL: July 1 - December 1). One rulebook in
    # transaction_windows.py. The AI caller runs inside the July pass; this
    # gate covers any future UI path and both engines identically.
    try:
        import transaction_windows as _tw
        from datetime import date as _date
        _d = as_of
        if _d is None and app is not None:
            _d = getattr(app, "current_date", None)
        _ok, _why = _tw.check_window("offer_sheet", _d)
        if not _ok:
            return {"ok": False, "reason": "window_closed", "detail": _why}
    except Exception:
        pass
    r = rng or random.Random()
    label, picks = offer_sheet_compensation(aav)
    year = int(getattr(league, "season_year", 2026) or 2026) + 1
    # Atomic compensation: gather every required pick FIRST and only
    # transfer once all are found. A shortfall fails the whole sheet
    # with nothing moved (previously the found picks transferred before
    # the missing check, leaving partial compensation behind).
    gathered = []
    missing = []
    for rnd in picks:
        pk = None
        # Walk forward through the signing club's OWN upcoming picks (as
        # far as picks exist -- seven drafts out). Real compensation is
        # the club's own picks in the coming drafts, so a near pick
        # that's already been traded just pushes that piece of the debt
        # to the next one the club still owns. Only when the club owns
        # none of the required picks at all is the sheet unsigned.
        for _yy in range(year, year + 7):
            pk = _own_pick(offering_team, _yy, rnd)
            if pk is not None and not any(pk is gp for gp in gathered):
                break
            pk = None
        if pk is None:
            missing.append(rnd)
        else:
            gathered.append(pk)
    if missing:
        return {"ok": False, "reason": "missing_own_picks",
                "missing_rounds": missing}

    # --- Trade alternative (the sign-and-trade door) -------------------
    # Before the compensation executes, check whether both clubs would
    # rather do a trade: the original club takes a player/prospect
    # package instead of the comp picks, the offering club gives players
    # instead of picks. AI-AI resolves immediately; a user-involved club
    # gets the choice (inbox message for the original club, a dialog for
    # the offering club when a UI is present). When no trade is agreed
    # the compensation below executes exactly as today.
    if not _skip_trade_alt and not expired:
        _alt = consider_offer_sheet_trade_alternative(
            app, league, offering_team, original_team, player, aav, years,
            gathered, rng=r)
        if _alt.get("agreed"):
            _user_side = _alt.get("user_side")
            if _user_side == "original":
                # The user's call: queue the choice, defer the
                # compensation until the inbox decision (or its expiry,
                # which defaults to the picks).
                _queue_offer_sheet_trade_alt(
                    app, league, offering_team, original_team, player,
                    aav, years, _alt)
                return {"ok": True, "pending_trade_choice": True,
                        "story": _alt.get("queued_story", "")}
            if _user_side == "offering":
                if _ask_user_offering_trade_alt(
                        app, offering_team, original_team, player, aav,
                        years, _alt):
                    _tres = execute_offer_sheet_trade(
                        league, offering_team, original_team, player,
                        aav, years, _alt, app=app)
                    if _tres is not None:
                        return _tres
                # Declined (or no interactive UI): the compensation
                # executes exactly as today.
            else:
                _tres = execute_offer_sheet_trade(
                    league, offering_team, original_team, player,
                    aav, years, _alt, app=app)
                if _tres is not None:
                    return _tres
                # The trade can't complete (cap/veto/freeze): fall
                # through to the compensation exactly as today.
    transferred = []
    for pk in gathered:
        _transfer_pick(pk, offering_team, original_team)
        transferred.append(pk)

    # Move the player.
    for t in getattr(league, "teams", []) or []:
        roster = getattr(t, "roster", None)
        if roster is not None and player in roster:
            try:
                player.last_team_name = _team_name(t)
            except Exception:
                pass
            try:
                roster.remove(player)
            except Exception:
                pass
    try:
        getattr(offering_team, "roster").append(player)
    except Exception:
        pass
    _sign_player(offering_team, player, aav, years)
    try:
        player.offer_sheet_pending = False
    except Exception:
        pass

    pname = getattr(player, "full_name", getattr(player, "name", "Unknown"))
    oname = _team_name(offering_team)
    tname = _team_name(original_team)
    story = (f"✍️ OFFER SHEET: {oname} sign {pname} "
             f"(${aav:,}/yr × {years}y). {tname} declined to match — "
             f"compensation: {label}.")
    if app is not None:
        try:
            app.add_news(story)
        except Exception:
            pass
    # Market: an offer sheet is a real signing -- star offer sheets move
    # future comparable asks, exactly like user/AI/MP signings.
    _register_market_signing(league, player, aav)
    # Reputation: the existing heat/grudge hooks.
    try:
        import reputation_system as _rep
        _rep.record_offer_sheet(
            getattr(league, "rivalries", []), offering_team, original_team,
            player, aav)
    except Exception:
        pass
    # Rivalry lifecycle: an offer sheet is a transfer -- his personal
    # beefs follow him to the offering club; ambient noise cools.
    try:
        import reputation_system as _rep2
        _rivs = getattr(league, "rivalries", None)
        if isinstance(_rivs, list):
            _rep2.on_player_transfer(_rivs, player, from_team=original_team,
                                     to_team=offering_team)
    except Exception:
        pass
    # Dressing room: poaching a man shakes the new room -- the room
    # reacts to WHO he is, bounded.
    try:
        import dressing_room as _dr_arr
        _dr_arr.cascade_on_arrival(offering_team, player, how="offer sheet")
    except Exception:
        pass
    return {"ok": True, "compensation": label, "picks": transferred,
            "story": story}


# ---------------------------------------------------------------------------
# Offer-sheet trade alternative (the sign-and-trade door)
# ---------------------------------------------------------------------------

def consider_offer_sheet_trade_alternative(app, league, offering_team,
                                           original_team, player, aav: int,
                                           years: int, compensation_picks,
                                           rng=None) -> Dict[str, Any]:
    """Clean boolean + package decision: would both clubs rather do a
    sign-and-trade than the pick compensation?

    The original club (declined to match -- not trying to keep him)
    takes the trade only if a player/prospect package from the offering
    club beats the comp picks' trade value (>= comp_value *
    OFFER_SHEET_TRADE_ASK_MULT): a live player beats mystery picks.
    The offering club gives players/prospects instead of its picks only
    if the package costs at most comp_value *
    OFFER_SHEET_TRADE_GIVE_UP_MULT. Both clubs must stay cap-legal.

    Returns {"agreed": bool, "package": [players], "comp_value": int,
    "package_value": int, "comp_label": str, "package_names": [str],
    "user_side": None | "original" | "offering"}. Pure evaluation -- it
    moves nothing. Not a negotiation engine: one package, take it or
    leave it.
    """
    import trade_engine as _te
    no = {"agreed": False, "package": [], "comp_value": 0,
          "package_value": 0, "comp_label": "", "package_names": [],
          "user_side": None}

    def _no_with_comp(comp_value=0, comp_label=""):
        # Negative answers still carry the computed compensation value
        # so callers (and QA) can see WHY no package fit.
        d = dict(no)
        d["comp_value"] = int(comp_value)
        d["comp_label"] = comp_label
        return d

    try:
        comp_label, _bands = offer_sheet_compensation(aav)
        comp_value = sum(_te.pick_trade_value(pk)
                         for pk in (compensation_picks or []))
        if comp_value <= 0:
            return _no_with_comp()
        floor = comp_value * OFFER_SHEET_TRADE_ASK_MULT
        ceiling = comp_value * OFFER_SHEET_TRADE_GIVE_UP_MULT

        # Candidate package pieces: signed roster players of the
        # offering club whose clause (if any) doesn't veto the move.
        candidates = []
        for p in list(getattr(offering_team, "roster", []) or []):
            if p is player:
                continue
            if contract_expired(p):
                continue  # unsigned: the original club would inherit
            try:
                if _te.trade_vetoes(offering_team, original_team, [p]):
                    continue
            except Exception:
                pass
            try:
                v = int(_te.asset_value(p))
            except Exception:
                continue
            candidates.append((v, p))
        candidates.sort(key=lambda vp: vp[0])

        package = None
        for v, p in candidates:
            if v >= floor and v <= ceiling:
                package = [(v, p)]
                break
        if package is None:
            # Two-player combo: the cheapest pair inside the window.
            pool = candidates[:8]
            best = None
            for i in range(len(pool)):
                for j in range(i + 1, len(pool)):
                    tot = pool[i][0] + pool[j][0]
                    if floor <= tot <= ceiling:
                        if best is None or tot < best[0]:
                            best = (tot, [pool[i], pool[j]])
            if best is not None:
                package = best[1]
        if not package:
            return _no_with_comp(comp_value, comp_label)
        package_players = [p for _v, p in package]
        package_value = sum(v for v, _p in package)

        # Cap reality: the original club absorbs the package's hits; the
        # offering club sheds them and then signs the sheet AAV.
        try:
            pkg_hits = sum(int(_te._player_cap_hit(p))
                           for p in package_players)
        except Exception:
            pkg_hits = 0
        try:
            if _cap_room(original_team) < pkg_hits:
                return _no_with_comp(comp_value, comp_label)
            if _cap_room(offering_team) + pkg_hits < aav:
                return _no_with_comp(comp_value, comp_label)
        except Exception:
            pass

        try:
            _names = [str(getattr(p, "full_name",
                                 getattr(p, "name", "a player")))
                      for p in package_players]
        except Exception:
            _names = []
        user_side = None
        try:
            if _is_user_team(original_team):
                user_side = "original"
            elif _is_user_team(offering_team):
                user_side = "offering"
        except Exception:
            pass
        return {"agreed": True, "package": package_players,
                "comp_value": int(comp_value),
                "package_value": int(package_value),
                "comp_label": comp_label, "package_names": _names,
                "user_side": user_side}
    except Exception:
        return no


def execute_offer_sheet_trade(league, offering_team, original_team, player,
                              aav: int, years: int, alt: Dict[str, Any],
                              app=None) -> Optional[Dict[str, Any]]:
    """Execute the agreed sign-and-trade: the original club trades the
    RFA's rights to the offering club for the package, and the offering
    club signs him at the sheet terms.

    Cap, picks, and players all land through trade_engine.execute_trade
    (ownership, clause vetoes, cap legality, freeze gates -- Caleb's
    internals are called, never redesigned), then the standard signing
    path (_sign_player + market registration + the offer-sheet
    reputation/rivalry/dressing-room hooks, exactly like the
    compensation path). Emits the league news story.

    Returns None when the trade can't complete -- the caller falls back
    to pick compensation exactly as today.
    """
    import trade_engine as _te
    try:
        package = list(alt.get("package") or [])
        if not package:
            return None
        try:
            _cd = getattr(app, "current_date", None)
            _date_str = _cd.isoformat()[:10] if (
                _cd is not None and hasattr(_cd, "isoformat")) else ""
        except Exception:
            _date_str = ""
        # NHL sign-and-trade: the original club signs the RFA at the sheet
        # terms FIRST, then trades the signed player. This makes him
        # "available" for the dress-minimum gate (an unsigned RFA's rights
        # don't count as a roster player, which would incorrectly block
        # the trade).
        _sign_player(original_team, player, aav, years)
        done = _te.execute_trade(offering_team, original_team, package,
                                 [player], date_str=_date_str,
                                 league=league)
        if done is None or str(getattr(done, "summary", "")) \
                .startswith("BLOCKED"):
            # Trade failed: undo the signing (restore unsigned RFA state)
            try:
                c = getattr(player, "contract", None)
                if c is not None:
                    c.years_remaining = 0
            except Exception:
                pass
            return None
        # He signs with the offering club at the sheet terms (this also
        # clears the offer-sheet-pending flag).
        _sign_player(offering_team, player, aav, years)
        _register_market_signing(league, player, aav)
        try:
            import reputation_system as _rep
            _rep.record_offer_sheet(
                getattr(league, "rivalries", []), offering_team,
                original_team, player, aav)
        except Exception:
            pass
        try:
            import reputation_system as _rep2
            _rivs = getattr(league, "rivalries", None)
            if isinstance(_rivs, list):
                _rep2.on_player_transfer(_rivs, player,
                                         from_team=original_team,
                                         to_team=offering_team)
        except Exception:
            pass
        try:
            import dressing_room as _dr_arr
            _dr_arr.cascade_on_arrival(offering_team, player,
                                       how="offer sheet")
        except Exception:
            pass
        pname = getattr(player, "full_name",
                        getattr(player, "name", "Unknown"))
        _names = ", ".join(alt.get("package_names") or
                           [getattr(p, "full_name", "a player")
                            for p in package])
        story = (f"\U0001f501 SIGN-AND-TRADE: "
                 f"{_team_name(original_team)} trade {pname}'s rights to "
                 f"{_team_name(offering_team)} for {_names} instead of "
                 f"matching the ${_format_money(aav)}/yr x {years}y offer "
                 f"sheet (compensation was: "
                 f"{alt.get('comp_label', 'picks')}).")
        if app is not None:
            try:
                app.add_news(story)
            except Exception:
                pass
        return {"ok": True, "trade_alternative": True,
                "package": package, "story": story}
    except Exception:
        return None


def _ask_user_offering_trade_alt(app, offering_team, original_team, player,
                                 aav: int, years: int,
                                 alt: Dict[str, Any]) -> bool:
    """Synchronous choice for the user-as-offering club: accept the
    sign-and-trade package, or decline and let the pick compensation
    execute exactly as today. True = accept. False = decline, or no
    interactive UI available (headless callers fall through to the
    compensation). Separated for QA patching."""
    if app is None:
        return False
    try:
        # In-game facade (gating T2-Phase 0): styled card instead of an
        # OS-modal dialog. The surrounding offer-sheet resolution is
        # synchronous by design, so this stays on the blocking facade
        # rather than the async ask_card (restructure deferred to T2-Phase 2).
        from popup_system import messagebox as _mb
    except Exception:
        return False
    try:
        pname = getattr(player, "full_name",
                        getattr(player, "name", "Unknown"))
        _names = ", ".join(alt.get("package_names") or [])
        return bool(_mb.askyesno(
            "Trade alternative",
            f"{_team_name(original_team)} declined to match your offer "
            f"sheet on {pname} (${_format_money(aav)}/yr x {years}y), "
            f"but will trade his rights for {_names} instead of the "
            f"{alt.get('comp_label', 'pick compensation')}.\n\n"
            f"Accept the trade? (No = he signs and the picks transfer.)"))
    except Exception:
        return False


def _queue_offer_sheet_trade_alt(app, league, offering_team, original_team,
                                 player, aav: int, years: int,
                                 alt: Dict[str, Any]) -> None:
    """Interactive inbox message for the user-as-original club: accept
    the sign-and-trade package or take the pick compensation. Stamps a
    choice deadline; an unanswered message defaults to the picks via
    the daily sweep -- the compensation is never lost to inaction."""
    if app is None:
        return
    try:
        from game_classes import EmailMessage
    except Exception:
        return
    pname = getattr(player, "full_name", getattr(player, "name", "Unknown"))
    _names = ", ".join(alt.get("package_names") or [])
    try:
        from datetime import timedelta as _td
        _today = getattr(app, "current_date", None)
        if _today is not None and hasattr(_today, "isoformat"):
            _deadline = _today + _td(days=OFFER_SHEET_TRADE_WINDOW_DAYS)
            _deadline_iso = _deadline.isoformat()
            _deadline_txt = _deadline.strftime("%b %d, %Y")
        else:
            _deadline_iso, _deadline_txt = None, (
                f"{OFFER_SHEET_TRADE_WINDOW_DAYS} days from today")
    except Exception:
        _deadline_iso, _deadline_txt = None, (
            f"{OFFER_SHEET_TRADE_WINDOW_DAYS} days from today")
    msg = EmailMessage(
        sender=_team_name(offering_team),
        sender_type="System",
        subject=f"Trade alternative: {pname} -- players or picks?",
        content=(f"You declined to match the offer sheet on {pname} "
                 f"(${_format_money(aav)}/yr x {years}y). "
                 f"{_team_name(offering_team)} would rather trade for his "
                 f"rights than lose the {alt.get('comp_label', 'picks')}: "
                 f"they offer {_names} "
                 f"(~{_format_money(alt.get('package_value', 0))} in trade "
                 f"value).\n\n"
                 f"Accept the trade, or decline and take the pick "
                 f"compensation: {alt.get('comp_label', '')}.\n\n"
                 f"You have until {_deadline_txt} to decide -- if the "
                 f"clock runs out he walks for the picks."),
        category="Contracts",
        is_important=True,
        requires_response=True,
        game_date_sent=getattr(app, "current_date", None),
        action_type="offer_sheet_trade_alt",
        action_data={
            "player_id": getattr(player, "id", None),
            "offering_team_id": getattr(offering_team, "id", None),
            "original_team_id": getattr(original_team, "id", None),
            "aav": aav,
            "years": years,
            "compensation": alt.get("comp_label", ""),
            "package_player_ids": [getattr(p, "id", None)
                                   for p in (alt.get("package") or [])],
            "package_value": int(alt.get("package_value", 0) or 0),
            "comp_value": int(alt.get("comp_value", 0) or 0),
            "trade_deadline": _deadline_iso,
            "offering_team_name": _team_name(offering_team),
            "original_team_name": _team_name(original_team),
        },
    )
    try:
        app.send_email_to_user(msg)
    except Exception:
        pass


def _find_trade_alt_message(app, player_id):
    try:
        inbox = getattr(getattr(app, "user_team", None), "inbox", None)
        messages = getattr(inbox, "messages", None) or []
    except Exception:
        return None
    for m in messages:
        if (getattr(m, "action_type", None) == "offer_sheet_trade_alt"
                and not getattr(m, "action_done", False)
                and (m.action_data or {}).get("player_id") == player_id):
            return m
    return None


def apply_offer_sheet_trade_alt(app, league, player_id, accept: bool,
                                rng=None) -> Dict[str, Any]:
    """Apply the user's accept/decline on a queued trade alternative.

    Accept: run the sign-and-trade (falls back to the pick compensation
    if the trade can no longer complete). Decline: the compensation
    executes exactly as today. Either way the queued message is closed.
    """
    r = rng or random.Random()
    msg = _find_trade_alt_message(app, player_id)
    if msg is None:
        return {"ok": False, "reason": "no_pending_trade_alt"}
    data = msg.action_data or {}
    league_teams = getattr(league, "teams", []) or []
    offering = _find_team(league_teams, data.get("offering_team_id"),
                          data.get("offering_team_name"))
    original = _find_team(league_teams, data.get("original_team_id"),
                          data.get("original_team_name"))
    player = _find_player(league, original, player_id)
    if offering is None or original is None or player is None:
        return {"ok": False, "reason": "stale_trade_alt"}
    aav = int(data.get("aav", 0) or 0)
    years = int(data.get("years", 1) or 1)
    if accept:
        # Rebuild the exact package the user was shown.
        _wanted = set(data.get("package_player_ids") or [])
        _package = [p for p in
                    list(getattr(offering, "roster", []) or [])
                    if getattr(p, "id", None) in _wanted]
        _alt = {"package": _package,
                "package_names": [],
                "comp_label": data.get("compensation", ""),
                "package_value": int(data.get("package_value", 0) or 0),
                "comp_value": int(data.get("comp_value", 0) or 0)}
        try:
            _alt["package_names"] = [
                str(getattr(p, "full_name",
                            getattr(p, "name", "a player")))
                for p in _package]
        except Exception:
            pass
        res = execute_offer_sheet_trade(league, offering, original, player,
                                        aav, years, _alt, app=app)
        if res is None:
            # The trade can't complete anymore: compensation as today.
            res = execute_offer_sheet(league, offering, original, player,
                                      aav, years, app=app, rng=r,
                                      _skip_trade_alt=True)
            if not res.get("ok"):
                return {"ok": False,
                        "reason": res.get("reason", "failed")}
        story = res.get("story", "")
    else:
        res = execute_offer_sheet(league, offering, original, player, aav,
                                  years, app=app, rng=r,
                                  _skip_trade_alt=True)
        if not res.get("ok"):
            return {"ok": False, "reason": res.get("reason", "failed")}
        story = res.get("story", "")
    try:
        msg.action_done = True
    except Exception:
        pass
    return {"ok": True, "accepted": bool(accept), "story": story}


def ai_offer_sheet_target_score(offering_team, player, aav: int) -> float:
    """0..1 — how attractive this unsigned RFA is as an offer-sheet target."""
    try:
        ovr = float(player.overall_rating())
    except Exception:
        ovr = 75.0
    age = _age(player)
    if ovr < 78 or age >= 27:
        return 0.0
    market = _market_value(player)
    # Overpay appetite: only elite young RFAs justify the picks + premium.
    premium = aav / max(1, market)
    if premium > 1.35:
        return 0.0
    # The aggressor must fit the AAV inside its cap plan (reserve +
    # roster math intact) -- poaching is discretionary, never desperate.
    if aav > _spending_budget(offering_team, incoming=True):
        return 0.0
    score = (ovr - 78) / 12.0  # 0..1 across 78..90
    if age <= 24:
        score += 0.25
    if premium > 1.15:
        score -= 0.2
    return max(0.0, min(1.0, score))


def ai_match_decision(original_team, player, aav: int,
                      compensation_label: str) -> bool:
    """Would the AI club match? Real clubs match unless the AAV is far
    above the player's worth to them or the cap makes it impossible."""
    if aav > _spending_budget(original_team,
                                core=_is_core_keep(player)):
        # Can't match inside the plan: take the picks. (The rational
        # version of the Carolina/Aho outcome.)
        return False
    market = _market_value(player)
    if aav > market * 1.45:
        # Walk away and take the picks — the Carolina/Aho exception in
        # reverse; real clubs do this when the overpay is absurd.
        return False
    try:
        ovr = float(player.overall_rating())
    except Exception:
        ovr = 76.0
    # Core young players are virtually always matched.
    if ovr >= 84 and _age(player) <= 26:
        return True
    return aav <= market * 1.2


# ---------------------------------------------------------------------------
# Arbitration — execution
# ---------------------------------------------------------------------------

def comparable_salaries(league, player, n: int = 5) -> List[int]:
    """Comparable contracts: same position group, age ±2, signed AAVs."""
    pos = str(getattr(getattr(player, "primary_position", None),
                      "value", "") or "")
    age = _age(player)
    comps = []
    for team in getattr(league, "teams", []) or []:
        for p in getattr(team, "roster", []) or []:
            if p is player:
                continue
            c = getattr(p, "contract", None)
            if c is None or int(getattr(c, "years_remaining", 0) or 0) <= 0:
                continue
            ppos = str(getattr(getattr(p, "primary_position", None),
                               "value", "") or "")
            if ppos != pos:
                continue
            if abs(_age(p) - age) > 2:
                continue
            try:
                comps.append((abs(float(p.overall_rating())
                                  - float(player.overall_rating())),
                               int(c.salary or 0)))
            except Exception:
                continue
    comps.sort(key=lambda t: t[0])
    return [s for _, s in comps[:n] if s > 0]


def resolve_arbitration(league, team, player, filed_by: str = "player",
                        app=None, rng=None) -> Dict[str, Any]:
    """File, settle-or-hear, and apply the arbitration outcome.

    Real shape: ~95% of filings settle before the hearing at ~midpoint of
    the two filings (slight player lean); ~5% reach a hearing and get an
    arbitrator award. Walk-away exists ONLY for player-elected awards at or
    above $4.85M (48h window, player becomes a UFA) -- in practice it
    almost never happens, so the AI only walks away when the award lands
    well above the player's market value. No walk-away from club-elected
    awards, ever.
    """
    r = rng or random.Random()
    market = _market_value(player)
    # Filings: player asks above market, team offers below -- the real shape.
    ask = int(market * (1.10 + r.random() * 0.15))
    offer = int(market * (0.80 + r.random() * 0.10))
    pname = getattr(player, "full_name", getattr(player, "name", "Unknown"))
    tname = _team_name(team)

    if r.random() < ARBITRATION_HEARING_RATE:
        # The rare hearing: neutral arbitrator from the panel decides.
        comps = comparable_salaries(league, player)
        award = arbitrator_award(player, ask, offer, comps, r,
                                 filed_by=filed_by)
        aav = int(award["award_aav"])
        term = int(award["term_years"])
        how = (f"hearing before {award['arbitrator']} "
               f"(${ask:,}/${offer:,} filings)")
        settled = False
    else:
        award = settle_arbitration(ask, offer, r)
        aav = int(award["award_aav"])
        term = int(award["term_years"])
        how = "pre-hearing settlement"
        settled = True

    walked_away = False
    # The mythical walk-away: player-elected award at/above $4.85M AND
    # absurd vs market. AI clubs decide on the spot (rare); the user's club
    # gets the 48-hour choice via _queue_walk_away_choice (the caller
    # checks award["walk_away_available"]).
    if (filed_by == "player" and not settled
            and aav >= ARBITRATION_WALK_AWAY_AAV
            and aav > market * 1.35 and r.random() < 0.25
            and not _is_user_team(team)):
        walked_away = True
        _move_to_free_agents(league, player)
    else:
        _sign_player(team, player, aav, term)
    try:
        player.arbitration_filed = False
    except Exception:
        pass
    if walked_away:
        story = (f"\u2696\ufe0f ARBITRATION: {pname} awarded "
                 f"${aav:,}/yr -- {tname} walk away. He becomes a UFA.")
    elif settled:
        story = (f"\u2696\ufe0f ARBITRATION: {pname} settles with {tname} "
                 f"at ${aav:,}/yr x {term}y ({how}).")
    else:
        story = (f"\u2696\ufe0f ARBITRATION: {pname} awarded ${aav:,}/yr x "
                 f"{term}y ({how}).")
    if app is not None:
        try:
            app.add_news(story)
        except Exception:
            pass
    return {"award": award, "walked_away": walked_away, "story": story,
            "filed_by": filed_by, "settled": settled}


# ---------------------------------------------------------------------------
# User-team decisions (called by the inbox action handlers)
# ---------------------------------------------------------------------------

def apply_qualifying_decision(app, league, team, player_id,
                              qualify: bool, rng=None) -> Dict[str, Any]:
    """Apply the user's per-RFA qualifying decision from the inbox.

    qualify=True: extend the QO (rights retained), then run the player's
    July mechanics (offer-sheet risk, arbitration filing) via
    resolve_user_rfa. qualify=False: non-tendered -- the player becomes a
    UFA and moves to the free-agent pool.
    """
    r = rng or random.Random()
    player = _find_player(league, team, player_id)
    if player is None:
        return {"ok": False, "reason": "player_not_found"}
    pname = getattr(player, "full_name", getattr(player, "name", "Unknown"))
    if not qualify:
        try:
            player.qo_extended = False
        except Exception:
            pass
        _move_to_free_agents(league, player)
        story = (f"{_team_name(team)} decline to tender {pname} a qualifying "
                 f"offer. He becomes an unrestricted free agent.")
        if app is not None:
            try:
                app.add_news(story)
            except Exception:
                pass
        return {"ok": True, "qualified": False, "story": story}
    prior = int(getattr(getattr(player, "contract", None), "salary", 0) or 0)
    qo = qualifying_offer_amount(prior)
    try:
        player.qo_extended = True
        player.qo_amount = qo
    except Exception:
        pass
    story = (f"{_team_name(team)} extend {pname} a qualifying offer "
             f"(${qo:,}). His rights are retained.")
    if app is not None:
        try:
            app.add_news(story)
        except Exception:
            pass
    july = resolve_user_rfa(app, league, team, player, r)
    return {"ok": True, "qualified": True, "qo_amount": qo, "story": story,
            "july": july}


def resolve_user_rfa(app, league, team, player, rng=None) -> Dict[str, Any]:
    """July mechanics for one user-qualified RFA: offer-sheet risk, then
    arbitration filing at the real-life-calibrated rate.

    Returns what happened; queues interactive inbox messages for the
    decisions that are the user's (match/take picks, walk-away).
    """
    r = rng or random.Random()
    out: Dict[str, Any] = {"offer_sheet": None, "arbitration": None}
    pname = getattr(player, "full_name", getattr(player, "name", "Unknown"))

    # --- Offer-sheet risk -------------------------------------------------
    if not bool(getattr(player, "arbitration_filed", False)):
        for offering_team in getattr(league, "teams", []) or []:
            if offering_team is team or _is_user_team(offering_team):
                continue
            market = _market_value(player)
            aav = int(market * (1.05 + r.random() * 0.25)
                      * _scarcity_mult(league, player))
            score = ai_offer_sheet_target_score(offering_team, player, aav)
            if score <= 0:
                continue
            if r.random() > OFFER_SHEET_BASE_RATE * score:
                continue
            years = r.choice([1, 2, 3, 4, 5])
            label, _picks = offer_sheet_compensation(aav)
            # the player's side: he must want to sign the sheet (loyalty /
            # bad blood vetoes apply to the user's RFAs too)
            try:
                import player_decision as _pd
                _willing, _appeal, _why = _pd.player_accepts_offer_sheet(
                    player, offering_team, aav, years, team,
                    league=league, app=app, rng=r)
            except Exception:
                _willing, _why = True, []
            if not _willing:
                continue
            _queue_offer_sheet_match(app, league, offering_team, team,
                                     player, aav, years, label,
                                     player_reasons=_why)
            out["offer_sheet"] = {
                "offering_team": _team_name(offering_team),
                "aav": aav, "years": years, "compensation": label,
            }
            break  # one suitor per summer

    # --- Arbitration filing -----------------------------------------------
    # (Filing blocks offer sheets -- if he filed, the sheet above can't
    # have happened; the guard at the top enforces the real rule.)
    if arbitration_eligible(player) and contract_expired(player):
        ask_gap = 0.25
        prob = arbitration_filing_probability(player,
                                               {"ask_gap_pct": ask_gap})
        if r.random() <= prob:
            try:
                player.arbitration_filed = True
            except Exception:
                pass
            if app is not None:
                try:
                    app.add_news(
                        f"\u2696\ufe0f ARBITRATION FILED: {pname} elects "
                        f"salary arbitration.")
                except Exception:
                    pass
            res = resolve_arbitration(league, team, player,
                                      filed_by="player", app=app, rng=r)
            out["arbitration"] = res
            award = res.get("award", {})
            if (res.get("walk_away_available", False)
                    or award.get("walk_away_available", False)):
                _queue_walk_away_choice(app, league, team, player, award)
    return out


def _queue_walk_away_choice(app, league, team, player,
                            award: dict) -> None:
    """The 48-hour walk-away window, as an inbox decision. Real life: only
    for player-elected awards at/above $4.85M; effectively never used."""
    if app is None:
        return
    try:
        from game_classes import EmailMessage
    except Exception:
        return
    pname = getattr(player, "full_name", getattr(player, "name", "Unknown"))
    aav = int(award.get("award_aav", 0) or 0)
    msg = EmailMessage(
        sender="League Office",
        sender_type="System",
        subject=f"Walk-away window: {pname} arbitration award",
        content=(f"The arbitrator awarded {pname} ${_format_money(aav)}/yr. "
                 f"You have 48 hours to walk away -- he would become an "
                 f"unrestricted free agent. Otherwise the award is binding."),
        category="Contracts",
        is_important=True,
        is_urgent=True,
        requires_response=True,
        action_type="arbitration_walkaway",
        action_data={"player_id": getattr(player, "id", None),
                     "team_id": getattr(team, "id", None),
                     "award_aav": aav,
                     "term_years": int(award.get("term_years", 1) or 1)},
    )
    try:
        app.send_email_to_user(msg)
    except Exception:
        pass


def apply_walk_away(app, league, team, player_id,
                    walk_away: bool) -> Dict[str, Any]:
    """Apply the user's walk-away decision. Walking away makes the player
    a UFA; accepting signs him at the awarded terms."""
    player = _find_player(league, team, player_id)
    if player is None:
        return {"ok": False, "reason": "player_not_found"}
    pname = getattr(player, "full_name", getattr(player, "name", "Unknown"))
    if walk_away:
        _move_to_free_agents(league, player)
        story = (f"{_team_name(team)} walk away from {pname}'s arbitration "
                 f"award. He becomes an unrestricted free agent.")
    else:
        story = (f"{_team_name(team)} accept {pname}'s arbitration award.")
    if app is not None:
        try:
            app.add_news(story)
        except Exception:
            pass
    return {"ok": True, "walked_away": walk_away, "story": story}


def _offer_sheet_deadline(msg, app=None):
    """The real match deadline for a queued offer-sheet message.

    Prefers the stamped match_deadline in action_data; falls back to
    game_date_sent + 7 days; None when neither is known (e.g. old saves --
    those are never auto-resolved). Trade-alternative messages stamp
    "trade_deadline" instead -- read either key.
    """
    data = getattr(msg, "action_data", None) or {}
    iso = data.get("match_deadline") or data.get("trade_deadline")
    if iso:
        try:
            from datetime import date as _d
            return _d.fromisoformat(str(iso))
        except Exception:
            pass
    sent = getattr(msg, "game_date_sent", None)
    if sent is not None and hasattr(sent, "toordinal"):
        try:
            from datetime import timedelta as _td
            return sent + _td(days=OFFER_SHEET_MATCH_WINDOW_DAYS)
        except Exception:
            pass
    return None


def _offer_sheet_expired(msg, app) -> bool:
    """True when the 7-day match clock has run out."""
    try:
        today = getattr(app, "current_date", None)
    except Exception:
        return False
    if today is None or not hasattr(today, "toordinal"):
        return False  # not a real calendar date: never auto-resolve
    deadline = _offer_sheet_deadline(msg, app)
    return bool(deadline is not None and today > deadline)


def process_offer_sheet_deadlines(app, league) -> int:
    """Daily sweep: any offer-sheet match decision whose 7-day clock has
    run out resolves as a decline -- the player goes to the offering club
    at the sheet terms (real CBA rule), compensation transfers, cap is
    registered. Idempotent; only touches expired, unanswered sheets.
    Trade-alternative choices ("offer_sheet_trade_alt") whose own clock
    has run out default to the pick compensation, exactly as today.
    Called once per day-advance from the daily loop.
    """
    if app is None or league is None:
        return 0
    try:
        inbox = getattr(getattr(app, "user_team", None), "inbox", None)
        messages = list(getattr(inbox, "messages", None) or [])
    except Exception:
        return 0
    resolved = 0
    for m in messages:
        if getattr(m, "action_type", None) == "offer_sheet_trade_alt":
            if getattr(m, "action_done", False):
                continue
            if not _offer_sheet_expired(m, app):
                continue
            data = getattr(m, "action_data", None) or {}
            res = apply_offer_sheet_trade_alt(
                app, league, data.get("player_id"), False)
            if res.get("ok"):
                resolved += 1
                if app is not None:
                    try:
                        app.add_news(
                            f"\u23f0 Trade-alternative clock expired: "
                            f"{_team_name(_find_team(getattr(league, 'teams', []), data.get('original_team_id'), data.get('original_team_name')))} "
                            f"takes the pick compensation.")
                    except Exception:
                        pass
            continue
        if getattr(m, "action_type", None) != "offer_sheet_match":
            continue
        if getattr(m, "action_done", False):
            continue
        if not _offer_sheet_expired(m, app):
            continue
        data = getattr(m, "action_data", None) or {}
        res = apply_offer_sheet_match(app, league,
                                      data.get("player_id"), False)
        if res.get("ok"):
            resolved += 1
            if app is not None:
                try:
                    app.add_news(
                        f"\u23f0 Offer-sheet clock expired: "
                        f"{_team_name(_find_team(getattr(league, 'teams', []), data.get('original_team_id'), data.get('original_team_name')))} "
                        f"did not match in time.")
                except Exception:
                    pass
    return resolved


def apply_offer_sheet_match(app, league, player_id, match: bool,
                            rng=None) -> Dict[str, Any]:
    """Apply the user's match/take-picks decision on an offer sheet.

    Finds the pending offer-sheet inbox message for the player to recover
    the offering team and terms. If the 7-day match clock has already run
    out, the decision is moot: the sheet resolves as a decline (player
    goes to the offering club at the sheet terms), exactly the real rule.
    """
    r = rng or random.Random()
    msg = _find_offer_sheet_message(app, player_id)
    if msg is None:
        return {"ok": False, "reason": "no_pending_offer_sheet"}
    expired = _offer_sheet_expired(msg, app)
    if expired:
        match = False  # the clock ran out -- he walks for the picks
    data = msg.action_data or {}
    league_teams = getattr(league, "teams", []) or []
    offering = _find_team(league_teams, data.get("offering_team_id"),
                          data.get("offering_team_name"))
    original = _find_team(league_teams, data.get("original_team_id"),
                          data.get("original_team_name"))
    player = _find_player(league, original, player_id)
    if offering is None or original is None or player is None:
        return {"ok": False, "reason": "stale_offer_sheet"}
    aav = int(data.get("aav", 0) or 0)
    years = int(data.get("years", 1) or 1)
    if match:
        # Match: keep the player at the offer-sheet terms. He can't be
        # traded for a year without his consent (modeled as a flag the
        # trade engine can honor). Cap is registered so the market
        # engine learns, exactly like every other signing.
        res = apply_offer_sheet_matched(league, offering, original, player,
                                        aav, years, app=app)
        story = res.get("story", "")
    else:
        res = execute_offer_sheet(league, offering, original, player, aav,
                                  years, app=app, rng=r, expired=expired)
        if not res.get("ok"):
            return {"ok": False, "reason": res.get("reason", "failed")}
        story = res.get("story", "")
        if expired:
            story = (f"The 7-day match window expired with no decision -- "
                     f"{story}")
    try:
        msg.action_done = True
    except Exception:
        pass
    return {"ok": True, "matched": match, "expired": expired, "story": story}


def _cap_room(team) -> float:
    """Spendable cap room under the REAL accounting.

    Uses salary_cap_system.cap_breakdown -- the same numbers the user's
    day-advancement compliance blocker enforces (roster + buyouts +
    retained + dead cap). Falls back to the roster-only Team.cap_space
    property if the cap module is unavailable.
    """
    try:
        from salary_cap_system import cap_breakdown
        bd = cap_breakdown(team)
        return float(bd.get("space", 0) or 0)
    except Exception:
        try:
            return float(getattr(team, "cap_space", 0) or 0)
        except Exception:
            return 0.0


# --- Cap consciousness: how real GMs think about the cap -----------------
# A hard "never over" gate stops insolvency, but real GMs do more: they
# keep an operating reserve (~1.5% of the cap) for callups, injuries and
# deadline accrual, and they never spend a dollar they need to fill out
# the roster at league minimum. Core keeps may dip into the reserve;
# everything discretionary must preserve it.
CAP_RESERVE_PCT = 0.015
LEAGUE_MIN_SALARY = 775_000
MIN_ROSTER_SIZE = 20


def _reserve_amount(team) -> float:
    try:
        cap = float(getattr(team, "salary_cap", 0) or 0)
    except Exception:
        cap = 0
    if cap <= 0:
        cap = 104_000_000
    return cap * CAP_RESERVE_PCT


def _is_core_keep(player) -> bool:
    """Players a real GM spends into the reserve to keep."""
    try:
        ovr = float(player.overall_rating())
    except Exception:
        ovr = 70.0
    return ovr >= 82 or (_age(player) <= 24 and ovr >= 78)


def _spending_budget(team, core: bool = False,
                     incoming: bool = False) -> float:
    """Max a rational GM spends here. After the spend the club can still
    fill a viable roster at league minimum; non-core spending must also
    preserve the operating reserve. `incoming` for players not yet on
    the roster (offer-sheet poaches, pool signings)."""
    try:
        size = len(getattr(team, "roster", []) or []) + (1 if incoming else 0)
    except Exception:
        size = MIN_ROSTER_SIZE
    open_spots = max(0, MIN_ROSTER_SIZE - size)
    need = open_spots * LEAGUE_MIN_SALARY
    if not core:
        need += _reserve_amount(team)
    return _cap_room(team) - need


def _find_player(league, team, player_id):
    if player_id is None:
        return None
    for t in getattr(league, "teams", []) or []:
        for p in getattr(t, "roster", []) or []:
            if getattr(p, "id", None) == player_id:
                return p
    # Also check the FA pool (non-tendered walk-aways).
    for p in getattr(league, "free_agents", []) or []:
        if getattr(p, "id", None) == player_id:
            return p
    return None


def _find_team(teams, team_id=None, team_name=None):
    """Find a team by id, falling back to team name.

    Team objects carry no id field (player ids are the stable identity;
    teams are identified by name everywhere else in the codebase, e.g.
    _own_pick and _transfer_pick), so the name is the reliable key here.
    """
    if team_id is not None:
        for t in teams or []:
            if getattr(t, "id", None) == team_id:
                return t
    if team_name:
        for t in teams or []:
            if _team_name(t) == team_name:
                return t
    return None


def _find_offer_sheet_message(app, player_id):
    try:
        inbox = getattr(getattr(app, "user_team", None), "inbox", None)
        messages = getattr(inbox, "messages", None) or []
    except Exception:
        return None
    for m in messages:
        if (getattr(m, "action_type", None) == "offer_sheet_match"
                and not getattr(m, "action_done", False)
                and (m.action_data or {}).get("player_id") == player_id):
            return m
    return None


def _ovr(player) -> float:
    try:
        return float(player.overall_rating())
    except Exception:
        return 70.0


def _ai_backfill_roster(team, league, r, target: int = 21) -> None:
    """Keep AI rosters whole after the UFA sweep.

    1. Promote the best signed prospects (2-year ELC-ish deals for the
       unsigned ones). 2. Sign cheap UFAs from the pool to 1-year deals.
    Never spends more than the available cap room.
    """
    roster = getattr(team, "roster", None)
    if roster is None:
        return
    try:
        import roster_limits as _rl
    except Exception:
        _rl = None
    prospects = sorted(getattr(team, "prospects", []) or [],
                       key=_ovr, reverse=True)
    for p in prospects:
        if len(roster) >= target:
            break
        # R1: never take a 51st contract -- the 50-SPC limit is hard.
        if _rl is not None and not _rl.ai_can_sign_spc(team):
            break
        # ELC promotions are how real cap-strapped teams fill holes --
        # allowed to dip into the reserve, but never below roster math.
        if _spending_budget(team, core=True, incoming=True) < 825_000:
            break
        c = getattr(p, "contract", None)
        if c is None or int(getattr(c, "years_remaining", 0) or 0) <= 0:
            _sign_player(team, p, 825_000, 2)
        try:
            getattr(team, "prospects").remove(p)
        except Exception:
            pass
        if p not in roster:
            roster.append(p)
    pool = getattr(league, "free_agents", []) or []
    guard = 0
    # The scarcity read depends only on (league, position group): cache it
    # per position for this backfill so a deep scan doesn't recompute the
    # whole market per player (perf cliff on big FA pools).
    _scarc_cache: Dict[str, float] = {}
    while len(roster) < target and pool and guard < 40:
        guard += 1
        # R1: never take a 51st contract.
        if _rl is not None and not _rl.ai_can_sign_spc(team):
            break
        budget = _spending_budget(team, incoming=True)
        if budget < LEAGUE_MIN_SALARY:
            break  # nothing in the pool is affordable -- skip the scan
        best = None
        for p in sorted(pool, key=_market_value):
            # Scarcity rides along: filling a hole at a thin position
            # costs what the market demands (capped at cheap-depth money).
            try:
                _g = str(getattr(getattr(p, "primary_position", ""),
                                 "value", "") or "")
            except Exception:
                _g = ""
            if _g not in _scarc_cache:
                _scarc_cache[_g] = _scarcity_mult(league, p)
            ask = min(int(_market_value(p) * _scarc_cache[_g]),
                      1_500_000)
            if ask <= budget:
                best = (p, ask)
                break
        if best is None:
            break
        p, ask = best
        _sign_player(team, p, ask, 1)
        try:
            pool.remove(p)
        except Exception:
            pass
        if p not in roster:
            roster.append(p)


def _is_two_way(player) -> bool:
    c = getattr(player, "contract", None)
    try:
        return bool(getattr(c, "two_way", False))
    except Exception:
        return False


def _ai_cap_compliance_sweep(team) -> int:
    """Demote until cap-compliant. Returns number of paper moves made."""
    try:
        from salary_cap_system import cap_breakdown
    except Exception:
        return 0
    moves = 0
    for _ in range(30):  # hard guard
        try:
            bd = cap_breakdown(team)
        except Exception:
            break
        if not bd.get("over_cap"):
            break
        roster = list(getattr(team, "roster", []) or [])
        if not roster:
            break
        # Two-ways first (fully exempt in the minors), then the biggest
        # remaining hits -- the standard paper-move order.
        roster.sort(key=lambda p: (0 if _is_two_way(p) else 1,
                                   -float(getattr(getattr(p, "contract", None),
                                                  "salary", 0) or 0)))
        p = roster[0]
        try:
            getattr(team, "roster").remove(p)
            ahl = getattr(team, "ahl_roster", None)
            if ahl is not None and p not in ahl:
                ahl.append(p)
            moves += 1
        except Exception:
            break
    return moves
