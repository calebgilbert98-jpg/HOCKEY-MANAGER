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


def _sign_player(team, player, aav: int, years: int) -> None:
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


def _ai_rfa_deal(player, qo_amount: int, rng) -> Tuple[int, int]:
    """AI club re-signs its qualified RFA: most sign near the QO or a
    short market deal; bridge deals for the young and good."""
    market = _market_value(player)
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
        aav, years = _ai_rfa_deal(player, qo, r)
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
                market = _market_value(player)
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
            aav = int(market * (1.05 + r.random() * 0.25))
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
                try:
                    player.offer_sheet_pending = False
                except Exception:
                    pass
                if app is not None:
                    try:
                        app.add_news(
                            f"\u270d\ufe0f OFFER SHEET: {_team_name(offering_team)} "
                            f"sign {getattr(player, 'full_name', '?')} "
                            f"(${aav:,}/yr x {years}y) -- "
                            f"{_team_name(original_team)} match.")
                    except Exception:
                        pass
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
        aav, years = _ai_rfa_deal(player, qo, r)
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
    (7-day clock, as in real life)."""
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
    msg = EmailMessage(
        sender=_team_name(offering_team),
        sender_type="System",
        subject=f"Offer sheet: {pname} — match or take picks?",
        content=(f"{_team_name(offering_team)} have signed your RFA {pname} "
                 f"to an offer sheet: ${_format_money(aav)}/yr x {years}y.\n\n"
                 f"Match it and keep him at those terms (he can't be traded "
                 f"for a year without his consent), or decline and take the "
                 f"compensation: {compensation_label}.\n\n"
                 f"You have 7 days to decide.{intel}"),
        category="Contracts",
        is_important=True,
        is_urgent=True,
        requires_response=True,
        action_type="offer_sheet_match",
        action_data={
            "player_id": getattr(player, "id", None),
            "offering_team_id": getattr(offering_team, "id", None),
            "original_team_id": getattr(original_team, "id", None),
            "aav": aav,
            "years": years,
            "compensation": compensation_label,
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
                        as_of=None) -> Dict[str, Any]:
    """Sign an unsigned RFA to an offer sheet.

    Moves the player, transfers the real compensation picks, feeds the
    existing reputation hooks (record_offer_sheet), and posts league news.
    Matching is the caller's decision — call this only for the signed
    outcome (matched = player stays; unmatched = this runs).

    as_of: the date the window is judged on. The July RFA pass runs while
    the stamped game date is still late June, so it passes July 1
    explicitly (the pass models July mechanics).
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
    transferred = []
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
            if pk is not None:
                break
        if pk is None:
            missing.append(rnd)
        else:
            _transfer_pick(pk, offering_team, original_team)
            transferred.append(pk)
    if missing:
        return {"ok": False, "reason": "missing_own_picks",
                "missing_rounds": missing}

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
    try:
        _cap_sys = getattr(league, "salary_cap_system", None)
        if _cap_sys is not None:
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
                pname, aav, _ovr100, _pos_name,
                int(getattr(player, "age", 27) or 27),
                int(getattr(league, "season_year", 0) or 0))
    except Exception:
        pass
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
            aav = int(market * (1.05 + r.random() * 0.25))
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


def apply_offer_sheet_match(app, league, player_id, match: bool,
                            rng=None) -> Dict[str, Any]:
    """Apply the user's match/take-picks decision on an offer sheet.

    Finds the pending offer-sheet inbox message for the player to recover
    the offering team and terms.
    """
    r = rng or random.Random()
    msg = _find_offer_sheet_message(app, player_id)
    if msg is None:
        return {"ok": False, "reason": "no_pending_offer_sheet"}
    data = msg.action_data or {}
    league_teams = getattr(league, "teams", []) or []
    offering = _find_team(league_teams, data.get("offering_team_id"))
    original = _find_team(league_teams, data.get("original_team_id"))
    player = _find_player(league, original, player_id)
    if offering is None or original is None or player is None:
        return {"ok": False, "reason": "stale_offer_sheet"}
    pname = getattr(player, "full_name", getattr(player, "name", "Unknown"))
    aav = int(data.get("aav", 0) or 0)
    years = int(data.get("years", 1) or 1)
    if match:
        # Match: keep the player at the offer-sheet terms. He can't be
        # traded for a year without his consent (modeled as a flag the
        # trade engine can honor).
        _sign_player(original, player, aav, years)
        try:
            player.offer_sheet_match_no_trade_until = int(
                getattr(league, "season_year", 2026) or 2026) + 1
        except Exception:
            pass
        story = (f"{_team_name(original)} match the offer sheet for {pname} "
                 f"(${aav:,}/yr x {years}y).")
    else:
        res = execute_offer_sheet(league, offering, original, player, aav,
                                  years, app=app, rng=r)
        if not res.get("ok"):
            return {"ok": False, "reason": res.get("reason", "failed")}
        story = res.get("story", "")
    try:
        msg.action_done = True
    except Exception:
        pass
    return {"ok": True, "matched": match, "story": story}


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


def _find_team(teams, team_id):
    for t in teams or []:
        if getattr(t, "id", None) == team_id:
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
    prospects = sorted(getattr(team, "prospects", []) or [],
                       key=_ovr, reverse=True)
    for p in prospects:
        if len(roster) >= target:
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
    while len(roster) < target and pool and guard < 40:
        guard += 1
        budget = _spending_budget(team, incoming=True)
        best = None
        for p in sorted(pool, key=_market_value):
            ask = min(_market_value(p), 1_500_000)
            if ask <= budget and budget >= LEAGUE_MIN_SALARY:
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
