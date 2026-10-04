# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""
salary_cap_system.py -- Dynamic NHL salary cap and contract market system.

The cap tracks the real NHL's announced path: $95.5M (2025-26) -> $104M
(2026-27) -> $113.5M (2027-28). Beyond the announced window it grows
~2-4% per year.
Player salary demands are expressed as a percentage of the cap, so when the
cap rises, new contract demands rise with it. Existing contracts are NOT
retroactively changed (like the real NHL).

Market-setting contracts: when a star (85+ OVR on the 1-100 display scale,
i.e. ~85+ on the native 100 scale) signs a top-5 AAV deal, it "sets the
market". For the next 2 seasons, comparable players (similar OVR, position
group, age band) demand a 10-15% premium -- the McDavid effect.

This module has NO dependencies on game_classes (avoids circular imports).
"""

import random
from dataclasses import dataclass
from typing import (Dict, List, Optional)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CAP = 104_000_000          # 2026-27 NHL cap (modern day)
#: Salary floor (2026-27): $78.0M against the $104M cap -- the real NHL's
#: ~$26M cap-to-floor gap, rounded. Clubs must sit at or above it; the
#: day-advance gate (_floor_compliance_blocker) and AI auto-compliance
#: enforce it. D46 (Wave B).
SALARY_CAP_FLOOR = 78_000_000
MIN_CAP = 70_000_000              # Floor sanity bound
MAX_CAP = 200_000_000             # Ceiling sanity bound
MIN_GROWTH = 0.02                 # 2% minimum annual growth
MAX_GROWTH = 0.04                 # 4% maximum annual growth

# Announced future caps (league + NHLPA, Jan 2025): season_year -> cap.
# advance_cap_year() honors these before falling back to 2-4% growth.
ANNOUNCED_CAPS = {
    2027: 113_500_000,            # 2027-28 season
}

# Market-setter thresholds (OVR on the 1-100 display scale)
MARKET_SETTER_MIN_OVR = 85        # Must be a star to set the market
MARKET_SETTER_TOP_N = 5           # Must be a top-5 AAV to set the market
MARKET_COMP_SEASONS = 2           # Comps influence demands for 2 seasons
MARKET_PREMIUM_MIN = 0.10         # +10% minimum premium
MARKET_PREMIUM_MAX = 0.15         # +15% maximum premium

# Comparability windows for market comps
OVR_COMP_WINDOW = 4               # Within 4 OVR points (display scale)
AGE_COMP_WINDOW = 3               # Within 3 years of age


def cap_pct_to_dollars(cap_pct: float, cap: int) -> int:
    """Convert a cap percentage (e.g. 0.12) to dollars against a cap."""
    return int(cap_pct * cap)


def dollars_to_cap_pct(dollars: int, cap: int) -> float:
    """Convert a dollar figure to a cap percentage."""
    if cap <= 0:
        return 0.0
    return dollars / cap


def position_group(position: str) -> str:
    """Bucket a position into Forward / Defense / Goalie for comp matching."""
    p = (position or "").upper().strip()
    if "GOAL" in p or p in ("G", "GK"):
        return "Goalie"
    if "DEFEN" in p or p in ("LD", "RD", "D", "DEF"):
        return "Defense"
    return "Forward"


# ---------------------------------------------------------------------------
# Market comp record
# ---------------------------------------------------------------------------

@dataclass
class MarketComp:
    """A market-setting contract signed by a star player."""
    player_name: str
    aav: int                    # Average annual value in dollars
    cap_pct: float              # AAV as fraction of cap at signing
    ovr: int                    # OVR on 1-100 display scale
    position_group: str         # Forward / Defense / Goalie
    age: int
    season_signed: int          # Season year the deal was signed

    def to_dict(self) -> Dict:
        return {
            "player_name": self.player_name,
            "aav": self.aav,
            "cap_pct": self.cap_pct,
            "ovr": self.ovr,
            "position_group": self.position_group,
            "age": self.age,
            "season_signed": self.season_signed,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "MarketComp":
        return cls(
            player_name=d.get("player_name", "Unknown"),
            aav=int(d.get("aav", 0)),
            cap_pct=float(d.get("cap_pct", 0.0)),
            ovr=int(d.get("ovr", 0)),
            position_group=d.get("position_group", "Forward"),
            age=int(d.get("age", 27)),
            season_signed=int(d.get("season_signed", 0)),
        )


# ---------------------------------------------------------------------------
# Salary cap system
# ---------------------------------------------------------------------------

class SalaryCapSystem:
    """
    League-wide salary cap tracker with growth and market dynamics.

    Usage:
        cap_sys = SalaryCapSystem()                    # $104M default
        cap_sys = SalaryCapSystem(initial_cap=90_000_000)  # user override
        new_cap = cap_sys.advance_cap_year(2027)       # $113.5M announced
        cap_sys.register_signing("A. Matthews", 13_250_000, ovr=94,
                                 position="C", age=27, season=2026)
        premium = cap_sys.market_premium(ovr=92, position="LW", age=26,
                                         season=2026)  # e.g. 1.12
    """

    def __init__(self, initial_cap: int = DEFAULT_CAP,
                 seed: Optional[int] = None):
        self.current_cap: int = max(MIN_CAP, min(MAX_CAP, int(initial_cap)))
        self.initial_cap: int = self.current_cap
        self.cap_history: List[Dict] = []   # [{season, cap, growth_pct}]
        self.market_comps: List[MarketComp] = []
        self._rng = random.Random(seed)

    # -- cap growth --------------------------------------------------------

    def advance_cap_year(self, season_year: int) -> int:
        """
        Grow the cap for a new season. Called on season rollover.
        Returns the new cap. Honors the league's announced cap path
        ($113.5M for 2027-28); beyond that, growth is 2-4% with
        randomness. Occasionally (10%) the league has a flat year
        (0-1% growth) like the COVID flat-cap era.
        """
        if season_year in ANNOUNCED_CAPS:
            new_cap = ANNOUNCED_CAPS[season_year]
            actual_growth = (new_cap - self.current_cap) / self.current_cap
            self.current_cap = new_cap
            self.cap_history.append({
                "season": season_year,
                "cap": new_cap,
                "growth_pct": round(actual_growth * 100, 2),
            })
        else:
            roll = self._rng.random()
            if roll < 0.10:
                # Flat-cap year (COVID era precedent)
                growth = self._rng.uniform(0.0, 0.01)
            else:
                growth = self._rng.uniform(MIN_GROWTH, MAX_GROWTH)

            new_cap = int(self.current_cap * (1 + growth))
            new_cap = max(MIN_CAP, min(MAX_CAP, new_cap))
            # Round to nearest $100K for clean numbers
            new_cap = round(new_cap / 100_000) * 100_000

            actual_growth = (new_cap - self.current_cap) / self.current_cap
            self.current_cap = new_cap
            self.cap_history.append({
                "season": season_year,
                "cap": new_cap,
                "growth_pct": round(actual_growth * 100, 2),
            })

        # Expire old market comps (older than MARKET_COMP_SEASONS)
        self.market_comps = [
            c for c in self.market_comps
            if season_year - c.season_signed <= MARKET_COMP_SEASONS
        ]
        return new_cap

    # -- market-setting contracts ------------------------------------------

    def _top_aav_threshold(self) -> int:
        """AAV cutoff for top-5 deals: the 5th-highest comp, or a heuristic."""
        if len(self.market_comps) >= MARKET_SETTER_TOP_N:
            sorted_aavs = sorted((c.aav for c in self.market_comps),
                                 reverse=True)
            return sorted_aavs[MARKET_SETTER_TOP_N - 1]
        # Heuristic before we have enough comps: ~13% of cap
        # (roughly where top-5 NHL AAVs sit: Matthews $13.25M / $88M = 15%)
        return int(self.current_cap * 0.13)

    def register_signing(self, player_name: str, aav: int, ovr: int,
                         position: str, age: int, season: int) -> bool:
        """
        Record a signed contract. Returns True if it "set the market"
        (star player + top-5 AAV), False otherwise.

        Only market-setters are kept as comps; regular signings are ignored
        to keep the comp list meaningful.
        """
        is_star = ovr >= MARKET_SETTER_MIN_OVR
        is_top_aav = aav >= self._top_aav_threshold()

        if not (is_star and is_top_aav):
            return False

        comp = MarketComp(
            player_name=player_name,
            aav=int(aav),
            cap_pct=dollars_to_cap_pct(int(aav), self.current_cap),
            ovr=int(ovr),
            position_group=position_group(position),
            age=int(age),
            season_signed=int(season),
        )
        # Replace any existing comp for the same player (re-signing)
        self.market_comps = [c for c in self.market_comps
                             if c.player_name != player_name]
        self.market_comps.append(comp)
        # Keep the list bounded
        self.market_comps.sort(key=lambda c: c.aav, reverse=True)
        self.market_comps = self.market_comps[:20]
        return True

    def market_premium(self, ovr: int, position: str, age: int,
                       season: int) -> float:
        """
        Return the demand multiplier for a player based on active market comps.
        Returns 1.0 if no comparable market-setter exists.

        A comp applies if: same position group, within OVR_COMP_WINDOW,
        within AGE_COMP_WINDOW, and signed within MARKET_COMP_SEASONS.
        Premium scales with how far above the comp's cap% the player's
        talent suggests -- capped at MARKET_PREMIUM_MAX.
        """
        pg = position_group(position)
        best_premium = 0.0

        for comp in self.market_comps:
            if season - comp.season_signed > MARKET_COMP_SEASONS:
                continue
            if comp.position_group != pg:
                continue
            if abs(ovr - comp.ovr) > OVR_COMP_WINDOW:
                continue
            if abs(age - comp.age) > AGE_COMP_WINDOW:
                continue

            # The closer the player's OVR to the setter's, the fuller premium
            closeness = 1.0 - (abs(ovr - comp.ovr) / (OVR_COMP_WINDOW + 1))
            premium = MARKET_PREMIUM_MIN + (
                (MARKET_PREMIUM_MAX - MARKET_PREMIUM_MIN) * closeness
            )
            best_premium = max(best_premium, premium)

        return 1.0 + best_premium

    # -- cap-relative demands -----------------------------------------------

    def demand_for(self, base_cap_pct: float, ovr: int, position: str,
                   age: int, season: int, scarcity: float = 1.0) -> int:
        """Convert a base demand (as cap %) to dollars against the CURRENT cap,
        applying any market-setter premium. This is the single choke point
        for "what does this player ask for" -- all negotiation paths should
        flow through here so demands track the cap.

        scarcity: UFA/RFA market scarcity multiplier from
        fa_market_scarcity() (default 1.0 = no scarcity effect). Thin
        market + many suitors inflates the ask; a flooded pool softens it.
        Same multiplier for user and AI -- one market.
        """
        premium = self.market_premium(ovr, position, age, season)
        try:
            _s = float(scarcity or 1.0)
        except Exception:
            _s = 1.0
        _s = max(SCARCITY_MIN, min(SCARCITY_MAX, _s))
        return int(cap_pct_to_dollars(base_cap_pct, self.current_cap)
                   * premium * _s)

    # -- persistence ---------------------------------------------------------

    def to_dict(self) -> Dict:
        return {
            "current_cap": self.current_cap,
            "initial_cap": self.initial_cap,
            "cap_history": list(self.cap_history),
            "market_comps": [c.to_dict() for c in self.market_comps],
        }

    @classmethod
    def from_dict(cls, d: Optional[Dict]) -> "SalaryCapSystem":
        d = d or {}
        obj = cls(initial_cap=int(d.get("current_cap", DEFAULT_CAP)))
        obj.initial_cap = int(d.get("initial_cap", obj.current_cap))
        obj.cap_history = list(d.get("cap_history", []))
        obj.market_comps = [MarketComp.from_dict(c)
                            for c in d.get("market_comps", [])]
        return obj


# ---------------------------------------------------------------------------
# Central cap accounting (single source of truth)
# ---------------------------------------------------------------------------
# Every cap decision -- trade validation, the Next Day over-cap blocker,
# roster/cap UI, AI cap logic -- must flow through these helpers so the AI
# and the user always see identical numbers. All team attributes are read
# via getattr with zero defaults, so old saves without the newer fields
# simply report 0 (additive, never a redesign of Team.payroll).
#
# Total cap charge = NHL roster salaries (net of retained salary)
#                  + in-game buyout hits (current season)
#                  + in-game retained-salary hits (team.retained_salary)
#                  + seeded real-life buyout hits (2026-27)
#                  + seeded real-life retained salary (2026-27)
#                  + seeded real-life bonus overages (2026-27)


# Burial exemption (NHL rule, CBA Art. 50.5): a one-way contract assigned
# to the minors still counts against the cap, minus the league minimum
# + $375k. Two-way deals are fully buried -- the minor-league salary
# never touches the NHL cap. Prospects never count.
LEAGUE_MINIMUM_SALARY = 775000
# Fallback only (used when burial_exemption() itself throws). Real CBA
# Art. 50.5: league minimum + $375k.
BURY_EXEMPTION = 375000 + LEAGUE_MINIMUM_SALARY  # $1,150,000


# ---------------------------------------------------------------------------
# 2026 CBA (ratified Sept 2026, effective for the 2026-27 season through
# 2029-30). Additive: the legacy constants above stay for old callers.
# ---------------------------------------------------------------------------

# New-CBA league-minimum salary schedule, keyed by season_year
# (2026 == the 2026-27 season). Source: NHL.com, "What you need to know
# about the new NHL CBA". Existing contracts are grandfathered -- this
# schedule gates NEW deals only.
MINIMUM_SALARY_SCHEDULE = {
    2026: 850_000,    # 2026-27
    2027: 900_000,    # 2027-28
    2028: 950_000,    # 2028-29
    2029: 1_000_000,  # 2029-30
}

# New-CBA entry-level maximum compensation (Article 29 of the MOU).
# Starting in 2026-27 it is NO LONGER based on draft year: in each League
# Year the max annual aggregate (Paragraph 1 salary + signing bonus +
# games-played bonuses) is that season's league minimum + $175,000 --
# $1.025M in 2026-27, $1.075M in 2027-28, $1.125M in 2028-29
# (PuckPedia, "Entry Level Contract Maximum Compensation").
# Schedule A bonuses (up to $1M/yr) are modeled separately below.
def elc_max_annual_comp(season_year=None) -> int:
    """Max ELC compensation in a given season (new-CBA 9.3(a))."""
    sy = _season_year_or_current(season_year)
    if sy >= 2026:
        return league_minimum_salary(sy) + 175_000
    if sy >= 2024:
        return 975_000
    if sy >= 2022:
        return 950_000
    return 925_000


def elc_max_total(contract_years=3, season_year=None) -> int:
    """Max total base compensation for an ELC of the given length.

    The game models one flat salary for every contract year, so the
    legal max total is the signing season's max annual compensation
    times the term (e.g. $1.025M x 3 = $3.075M for a 2026-27 ELC).
    """
    yrs = max(1, min(3, int(contract_years or 3)))
    return elc_max_salary(yrs, season_year) * yrs


# 2026-27 cap the market bands were calibrated against.
_ASK_BAND_CAP = 104_000_000


def base_ask_dollars(ovr100: int, age: int, on_elc: bool = False,
                     position: str = "") -> int:
    """Base annual salary a player asks for, BEFORE market-setter premium.

    The 2026 summer market reset, shared by every negotiation path (user
    contract talks, AI free agency, AI extensions): superstar 95+ asks
    $14-19M, premium 90+ asks $9-13.5M -- the same bands the league's
    contracts were generated on and the AI's own estimate mirrors. Below
    the star tiers the regular youth / veteran / middle-class curves
    apply. A player can only sign one ELC, so a player currently on an
    ELC asks second-contract money, not the ELC band.

    Bands are fractions of the 2026 $104M cap, so callers dividing by
    the live cap get demands that scale as the cap climbs. Callers feed
    the result through SalaryCapSystem.demand_for for the market premium.
    """
    try:
        ovr100 = int(ovr100)
    except Exception:
        ovr100 = 75
    try:
        age = int(age)
    except Exception:
        age = 27
    if ovr100 >= 95:
        lo, hi, f = 14_000_000, 19_000_000, (ovr100 - 94) / 6
    elif ovr100 >= 90:
        lo, hi, f = 9_000_000, 13_500_000, (ovr100 - 89) / 6
    elif age <= 22 and not on_elc:
        # ELC-aged player asking for his (first) NHL deal.
        try:
            lo, hi = int(league_minimum_salary()), int(
                elc_max_salary(3 if age <= 21 else 2))
        except Exception:
            lo, hi = 775_000, 975_000
        f = (ovr100 - 62) / 28
    elif age <= 25 and ovr100 < 80:
        lo, hi, f = 1_200_000, 5_000_000, (ovr100 - 62) / 28
    elif age >= 33 and ovr100 < 84:
        try:
            _vlo = int(league_minimum_salary())
        except Exception:
            _vlo = 775_000
        lo, hi, f = _vlo, 3_750_000, (ovr100 - 62) / 28
    else:
        lo, hi, f = 1_000_000, 6_500_000, (ovr100 - 62) / 28
    f = max(0.0, min(1.0, f))
    base = lo + (hi - lo) * f
    # Generation is position-blind; the established estimate carries a
    # small positional nudge and the ask matches it.
    _pos = str(position or "").upper()
    if _pos.startswith("G"):
        base *= 1.1
    elif _pos.startswith("C"):
        base *= 1.05
    return int(base)


def elc_max_salary(contract_years=3, season_year=None) -> int:
    """Max flat salary for an ELC signed in the given season.

    The game models one salary for every year of a contract, so the
    faithful ceiling is the FIRST season's max -- the binding year,
    since the per-season max only rises after that.
    """
    return elc_max_annual_comp(season_year)


# 9.4 maximum minor-league compensation on an ELC, by draft year
# (MOU table: 2026/27 -> $87.5k; 2028/29 -> $90k; 2030 -> $92.5k).
def elc_minor_salary_max(draft_year=None) -> int:
    """Max AHL salary on an ELC for a prospect of the given draft year."""
    try:
        dy = int(draft_year if draft_year is not None
                 else _season_year_or_current())
    except (TypeError, ValueError):
        dy = _season_year_or_current()
    if dy >= 2030:
        return 92_500
    if dy >= 2028:
        return 90_000
    if dy >= 2026:
        return 87_500
    if dy >= 2024:
        return 85_000
    if dy >= 2022:
        return 82_500
    return 80_000

# New-CBA maximum contract term: 7 years re-signing with the same club,
# 6 years signing elsewhere as a free agent (was 8/7). Existing deals are
# grandfathered; these gate NEW contracts only.
MAX_TERM_RESIGN = 7
MAX_TERM_EXTERNAL = 6

# New-CBA AHL rule: a 19-year-old CHL player drafted in the FIRST ROUND
# may be loaned to the AHL. 18-year-olds and later-round picks still go
# back to junior. No per-team limit.
AHL_CHL_MIN_AGE = 19
AHL_CHL_FIRST_ROUND_ONLY = True


def _season_year_or_current(season_year=None) -> int:
    """Normalize a season_year; None infers from today's date."""
    if season_year is not None:
        try:
            return int(season_year)
        except (TypeError, ValueError):
            pass
    from datetime import date as _date
    _today = _date.today()
    # The NHL season turns over in September.
    return _today.year if _today.month >= 9 else _today.year - 1


def league_minimum_salary(season_year=None) -> int:
    """New-CBA league minimum for a season_year (2026 == 2026-27).

    Seasons before 2026 use the old $775k; seasons past the CBA window
    hold at $1M. Existing contracts are grandfathered -- callers must
    only apply this to NEW deals.
    """
    sy = _season_year_or_current(season_year)
    if sy < 2026:
        return LEAGUE_MINIMUM_SALARY
    if sy > 2029:
        return 1_000_000
    return MINIMUM_SALARY_SCHEDULE.get(sy, 1_000_000)


def burial_exemption(season_year=None) -> int:
    """Burial exemption (league minimum + $375k) for a season.

    Real NHL CBA Article 50.5: a team burying a one-way contract in the
    minors gets cap relief equal to the league minimum salary + $375,000
    (the "Burying Threshold"). E.g. 2026-27: $850k + $375k = $1.225M.
    """
    return 375_000 + league_minimum_salary(season_year)


# ---------------------------------------------------------------------------
# Entry-level contract negotiation
# ---------------------------------------------------------------------------
# An ELC is the one deal a prospect's camp actually negotiates: base salary
# inside the ELC band, a signing bonus (capped at 10% of base -- the real
# CBA's signing-bonus limit), and attainable performance bonuses
# (Schedule-A style, capped at $1M/yr). Term is NOT negotiable: it follows
# the signing-age table. All tuning here is a judgment call -- flag before
# changing.

ELC_SIGNING_BONUS_PCT = 0.10   # of base salary, per year
ELC_PERF_BONUS_MAX = 1_000_000  # per year, Schedule-A style
ELC_BASE_RESPECT = 0.80       # base < 80% of the ask's base -> insult, rejected
ELC_BONUS_WEIGHT = 0.5         # bonuses aren't guaranteed money


def elc_years_for_age(age) -> int:
    """Number of ELC years for a signing age (CBA 9.1(b) chart).

    18-21 -> 3 years; 22-23 -> 2 years; 24 -> 1 year; 25+ -> 0, meaning
    NOT in the Entry Level System at all. (The new CBA removed the old
    European 25-27 one-year exception, so this is uniform for every
    prospect.) Callers MUST refuse an ELC offer when this returns 0 --
    never clamp or fall through.
    """
    try:
        a = int(age or 0)
    except Exception:
        return 3
    if a <= 21:
        return 3
    if a <= 23:
        return 2
    if a == 24:
        return 1
    return 0


def elc_band(age, season_year=None):
    """(floor, ceiling, years) for an ELC signed at this age.

    Floor is the league minimum; ceiling is the 9.3(a) max annual
    compensation for the signing season. years == 0 means the player is
    NOT ELC-eligible (25+) -- the caller must refuse the offer.
    """
    years = elc_years_for_age(age)
    floor = int(league_minimum_salary(season_year))
    ceil = int(elc_max_annual_comp(season_year))
    return max(0, floor), max(floor, ceil), years


def _turns_20_late_in_signing_year(birth_date, signing_year) -> bool:
    """The 9.1(d) slide exception: a nominal 19-year-old (Sept-15 age)
    who turns 20 between September 16 and December 31 of the signing
    year never gets the automatic extension."""
    try:
        parts = str(birth_date or "").strip().split("-")
        by, bm, bd = int(parts[0]), int(parts[1]), int(parts[2])
        sy = int(signing_year)
    except (ValueError, TypeError, AttributeError, IndexError):
        return False
    if by != sy - 20:
        return False
    return (bm, bd) >= (9, 16)


def elc_slide_applies(signing_sept15_age, slides_used, seasons_completed,
                      nhl_games_this_season, birth_date=None,
                      signing_year=None) -> bool:
    """Whether an ELC slides at this season rollover (CBA 9.1(d)).

    - Signed at 18 or 19 (Sept-15 age) and played fewer than 10 NHL
      games in the first season under the SPC -> extend one year.
    - Signed at 18, slid after year one, fewer than 10 NHL games in the
      second season -> extend one more year (the double slide). The
      second slide REQUIRES the first: seasons_completed must equal
      slides_used (a slide happens at most once per completed season,
      only in the first one/two seasons).
    - Exception: a nominal 19-year-old who turns 20 between Sept 16 and
      Dec 31 of the signing year is never slide-eligible.
    Sliding extends Paragraph 1 salary and bonuses but NOT the signing
    bonus (already paid); the game models that by extending years only.
    """
    try:
        age = int(signing_sept15_age)
        used = int(slides_used or 0)
        done = int(seasons_completed or 0)
        gp = int(nhl_games_this_season or 0)
    except (TypeError, ValueError):
        return False
    if gp >= 10:
        return False
    if done != used:
        return False
    if age == 18:
        return done < 2
    if age == 19:
        if _turns_20_late_in_signing_year(birth_date, signing_year):
            return False
        return done < 1
    return False


def elc_prospect_ask(player, season_year=None) -> Dict:
    """The prospect camp's opening ask: salary, signing_bonus,
    performance_bonus, plus a flavor line.

    Pedigree anchors it (overall_pick / draft_round): a top-5 pick's camp
    asks for the max, a 7th-rounder's takes the floor. Selfishness
    (1-100, dealt at generation) pushes the ask up; anything unselfish
    pulls it toward the floor. All clamped to the ELC band.

    The band uses the CBA 9.2 Sept-15 signing age (deferred import --
    salary_cap_system can't import draft_generator at module level).
    """
    try:
        age = int(getattr(player, "age", 20) or 20)
    except Exception:
        age = 20
    try:
        from draft_generator import age_on_sept15 as _s15
        _sv = _s15(getattr(player, "birth_date", ""), season_year)
        if _sv is not None:
            age = _sv
    except Exception:
        pass
    floor, ceil, years = elc_band(age, season_year)
    span = max(1, ceil - floor)

    try:
        pick = int(getattr(player, "overall_pick", 0) or 0)
    except Exception:
        pick = 0
    try:
        rnd = int(getattr(player, "draft_round", 0) or 0)
    except Exception:
        rnd = 0
    if pick >= 1:
        if pick <= 5:
            pedigree, plabel = 1.0, "top-5 pick"
        elif pick <= 32:
            pedigree, plabel = 0.85, "first-rounder"
        elif pick <= 64:
            pedigree, plabel = 0.65, "second-rounder"
        elif pick <= 96:
            pedigree, plabel = 0.45, "third-rounder"
        else:
            pedigree, plabel = 0.25, "late-round pick"
    elif rnd >= 1:
        pedigree = {1: 0.85, 2: 0.65, 3: 0.45}.get(rnd, 0.25)
        plabel = {1: "first-rounder", 2: "second-rounder",
                  3: "third-rounder"}.get(rnd, "late-round pick")
    else:
        pedigree, plabel = 0.15, "undrafted free agent"

    try:
        selfish = float(getattr(player, "selfishness", 50) or 50)
    except Exception:
        selfish = 50.0
    selfish = max(1.0, min(100.0, selfish))

    ask_salary = floor + span * pedigree
    # Selfishness swings the ask up to +/-15% of the band around neutral.
    ask_salary += span * 0.15 * ((selfish - 50.0) / 50.0)
    ask_salary = max(floor, min(ceil, int(round(ask_salary))))

    if pick >= 1 and pick <= 32:
        ask_signing = int(round(ask_salary * ELC_SIGNING_BONUS_PCT))
    elif rnd in (2, 3) or (64 < pick <= 96):
        ask_signing = int(round(ask_salary * ELC_SIGNING_BONUS_PCT * 0.5))
    else:
        ask_signing = 0

    if pick >= 1 and pick <= 10:
        ask_perf = ELC_PERF_BONUS_MAX
    elif (pick >= 1 and pick <= 32) or rnd == 1:
        ask_perf = ELC_PERF_BONUS_MAX // 2
    elif rnd in (2, 3):
        ask_perf = ELC_PERF_BONUS_MAX // 4
    else:
        ask_perf = 0

    if pedigree >= 0.85:
        flavor = (f"As a {plabel}, his camp expects the full ELC -- max "
                  f"base, max signing bonus, and performance bonuses.")
    elif pedigree >= 0.45:
        flavor = (f"A {plabel}: his camp wants a strong ELC but knows "
                  f"he has to earn the top of the band.")
    else:
        flavor = (f"A {plabel}, he's just happy for the opportunity -- "
                  f"his camp isn't driving a hard bargain.")
    if selfish >= 70:
        flavor += " He's known to look after himself at the table."
    elif selfish <= 30:
        flavor += " By all accounts he's an easy sign."
    return {
        "salary": ask_salary,
        "signing_bonus": ask_signing,
        "performance_bonus": ask_perf,
        "years": years,
        "floor": floor,
        "ceiling": ceil,
        "flavor": flavor,
    }


def elc_offer_value(salary, signing_bonus, performance_bonus) -> int:
    """Comparable value of an ELC offer: base + signing bonus + half the
    performance bonus (bonuses aren't guaranteed money)."""
    try:
        return (int(salary or 0) + int(signing_bonus or 0)
                + int(int(performance_bonus or 0) * ELC_BONUS_WEIGHT))
    except Exception:
        return 0


def elc_handshake(ask: Dict, salary, signing_bonus, performance_bonus) -> Dict:
    """Resolve one ELC offer against the camp's ask.

    The base salary is the respect signal: meeting the ask's value signs
    him; a base that's clearly lowballed (< 80% of the ask's base) gets a
    flat rejection; anything in the neighborhood draws a counter at the
    full ask. Returns {verdict, counter, note}.
    """
    ask_value = elc_offer_value(ask["salary"], ask["signing_bonus"],
                                ask["performance_bonus"])
    offer_value = elc_offer_value(salary, signing_bonus, performance_bonus)
    if offer_value >= ask_value:
        return {"verdict": "accepted", "counter": None,
                "note": "The agent shakes your hand. Deal."}
    ask_base = ask["salary"] or 1
    if salary < ELC_BASE_RESPECT * ask_base and offer_value < 0.9 * ask_value:
        short = ask_value - offer_value
        return {"verdict": "rejected", "counter": None,
                "note": (f"Rejected -- you're about ${short:,} short of where "
                         f"his camp is. They'll listen to a better offer.")}
    return {"verdict": "counter", "counter": {
                "salary": ask["salary"],
                "signing_bonus": ask["signing_bonus"],
                "performance_bonus": ask["performance_bonus"],
                "years": ask["years"]},
            "note": ("Not quite -- the agent counters at his ask. "
                     "Take it or adjust your offer.")}


def max_contract_term(is_extension: bool) -> int:
    """New-CBA maximum term: 7 years to re-sign, 6 years externally."""
    return MAX_TERM_RESIGN if is_extension else MAX_TERM_EXTERNAL


def _on_waiver_wire(p) -> bool:
    """True while a player sits on the waiver wire awaiting clearing."""
    try:
        return bool(getattr(p, "on_waivers", False)) and int(getattr(p, "waiver_days", 0) or 0) > 0
    except Exception:
        return False


def _active_roster_hit(p) -> int:
    """Cap hit of a player on the NHL active roster: full salary.

    Wave B D45: the waiver wire no longer sheds cap space. A player on the
    wire counts his FULL hit until his waiver clears (real NHL). The old
    $0-while-on-wire rule was a loophole -- waive the $8M problem Monday,
    trade Tuesday at phantom space, reclaim him off the wire Thursday.
    Relief now comes only from the real outcomes: a claim (off the books
    entirely) or clearance + AHL assignment (burial rule). Waivers remain
    a logical compliance tool -- the day-advance blocker counts an
    in-flight wire at its expected post-clearing charge (compliance_charge)
    so corrective action isn't a soft-lock.
    """
    try:
        contract = getattr(p, "contract", None)
        if contract is not None:
            hit = int(getattr(contract, "salary", 0) or 0)
            hit -= int(getattr(p, "retained_amount", 0) or 0)
            return max(0, hit)
    except Exception:
        pass
    return 0


def _expected_wire_charge(p) -> int:
    """Cap charge a wire player will carry once his waiver clears (D45).

    Clearance auto-assigns to the AHL (main.py waiver processing), so the
    burial rule applies: two-way deals drop to $0, one-way deals keep hit
    minus the burial exemption. The day-advance compliance blocker counts
    this expected charge -- an in-flight corrective waive doesn't
    hard-block the day. Trade validation and cap_space always use the
    real current charge (full hit on the wire).
    """
    try:
        contract = getattr(p, "contract", None)
        if contract is None:
            return 0
        if bool(getattr(contract, "two_way", False)):
            return 0
        hit = int(getattr(contract, "salary", 0) or 0)
        hit -= int(getattr(p, "retained_amount", 0) or 0)
        try:
            _bury = burial_exemption()
        except Exception:
            _bury = BURY_EXEMPTION
        return max(0, hit - _bury)
    except Exception:
        return 0


def compliance_charge(team) -> int:
    """Cap charge for the day-advance compliance check (D45).

    Identical to total_cap_charge except players on the waiver wire count
    at their expected post-clearing charge (burial rule) instead of their
    full current hit: a pending corrective waive is corrective action in
    flight, not a reason to hard-block the day. Everything else -- trade
    validation, cap_space, the cap UI -- uses the real charge.
    """
    try:
        total = 0
        for p in (getattr(team, "roster", None) or []):
            try:
                total += (_expected_wire_charge(p) if _on_waiver_wire(p)
                          else _active_roster_hit(p))
            except Exception:
                continue
        for p in (getattr(team, "ahl_roster", None) or []):
            try:
                total += minor_league_cap_charge(p)
            except Exception:
                continue
        return max(0, total) + int(dead_cap_charge(team) or 0)
    except Exception:
        return 0


def floor_space(team) -> int:
    """Cap payroll above the salary floor (negative when under it). D46."""
    try:
        return int(total_cap_charge(team) or 0) - int(SALARY_CAP_FLOOR)
    except Exception:
        return 0


def minor_league_cap_charge(p) -> int:
    """Cap hit of a player under NHL contract assigned to the minors.

    True NHL rule: two-way deals count $0 (minor-league salary is cap
    exempt); one-way deals count salary minus the burial exemption.
    D45: the waiver-wire shed is gone everywhere -- a player on the wire
    counts his full hit until his waiver clears (see _active_roster_hit).
    """
    try:
        contract = getattr(p, "contract", None)
        if contract is None:
            return 0
        if bool(getattr(contract, "two_way", False)):
            return 0
        hit = int(getattr(contract, "salary", 0) or 0)
        hit -= int(getattr(p, "retained_amount", 0) or 0)
        # New CBA: the burial exemption floats with the league minimum
        # ($375k + minimum => $1.225M in 2026-27).
        try:
            _bury = burial_exemption()
        except Exception:
            _bury = BURY_EXEMPTION
        return max(0, hit - _bury)
    except Exception:
        return 0


def roster_cap_charge(team) -> int:
    """Active-roster cap charge under the true NHL rule (Eastside logic).

    Only the NHL active roster counts at full salary. Prospects never
    count. Players under NHL contract in the minors follow the burial
    rule: two-way deals are fully exempt, one-way deals count salary
    minus the burial exemption (league minimum + $375k, $1.225M in
    2026-27).

    Retained salary lowers the charge: a player carrying retained_amount
    (kept by his former club) counts salary - retained here, while the
    retaining club carries it as dead cap via retained_charge().
    """
    try:
        total = 0
        for p in (getattr(team, "roster", None) or []):
            total += _active_roster_hit(p)
        for p in (getattr(team, "ahl_roster", None) or []):
            total += minor_league_cap_charge(p)
        return max(0, total)
    except Exception:
        return 0


def in_game_buyout_charge(team, season_year=None) -> int:
    """Current-season buyout cap hits created by in-game buyouts."""
    try:
        hits = getattr(team, "buyout_cap_hits", None) or {}
        if season_year is None:
            return int(sum(hits.values()))
        return int(hits.get(season_year, 0) or 0)
    except Exception:
        return 0


def seeded_buyout_charge(team) -> int:
    """Seeded real-life 2026-27 buyout penalties (0 if cleared/expired)."""
    try:
        return int(getattr(team, "real_buyout_cap", 0) or 0)
    except Exception:
        return 0


def seeded_retained_charge(team) -> int:
    """Seeded real-life 2026-27 retained-salary penalties."""
    try:
        return int(getattr(team, "real_retained_salary", 0) or 0)
    except Exception:
        return 0


def seeded_overage_charge(team) -> int:
    """Seeded real-life 2026-27 bonus-overage penalties."""
    try:
        return int(getattr(team, "real_bonus_overage", 0) or 0)
    except Exception:
        return 0


def retained_charge(team) -> int:
    """In-game retained-salary dead cap (real NHL retained transactions).

    Each entry in team.retained_salary is dead money for its remaining
    term; expired entries are dropped by League.end_of_season().
    """
    try:
        ledger = getattr(team, "retained_salary", None) or []
        return int(sum(int(e.get("amount", 0) or 0)
                       for e in ledger
                       if int(e.get("seasons_remaining", 0) or 0) > 0))
    except Exception:
        return 0


def retention_slots_used(team) -> int:
    """Active retained-salary transactions (NHL max is 3 per club)."""
    try:
        ledger = getattr(team, "retained_salary", None) or []
        return sum(1 for e in ledger
                   if int(e.get("seasons_remaining", 0) or 0) > 0)
    except Exception:
        return 0


def dead_cap_charge(team, season_year=None) -> int:
    """All dead-cap penalties: in-game buyouts + seeded real-life penalties
    + in-game retained salary."""
    return (in_game_buyout_charge(team, season_year)
            + seeded_buyout_charge(team)
            + seeded_retained_charge(team)
            + seeded_overage_charge(team)
            + retained_charge(team))


def total_cap_charge(team, season_year=None) -> int:
    """Total cap burden: roster salaries + dead cap."""
    return roster_cap_charge(team) + dead_cap_charge(team, season_year)


def cap_space(team, season_year=None) -> int:
    """Cap room remaining (negative when over the cap)."""
    try:
        cap = int(getattr(team, "salary_cap", DEFAULT_CAP) or DEFAULT_CAP)
    except Exception:
        cap = DEFAULT_CAP
    return cap - total_cap_charge(team, season_year)


def is_over_cap(team, season_year=None) -> bool:
    """True when the club's total cap charge exceeds its cap."""
    return cap_space(team, season_year) < 0


def waiver_shed_charge(team) -> int:
    """Cap dollars temporarily shed by players on the waiver wire.

    RETIRED by Wave B D45: the wire no longer sheds cap space (real NHL --
    a player on the wire counts his full hit until his waiver clears).
    Kept as a zero-returning shim because the cap UI and windows.py
    reference it; the compliance blocker now uses compliance_charge().
    """
    return 0


def cap_breakdown(team, season_year=None) -> Dict:
    """Full component breakdown for cap UI screens."""
    roster = roster_cap_charge(team)
    # Buried one-way money in the minors, shown separately for transparency
    # (it is already included in the roster charge above).
    try:
        buried = sum(minor_league_cap_charge(p)
                     for p in (getattr(team, "ahl_roster", None) or []))
    except Exception:
        buried = 0
    # Cap dollars temporarily shed by players sitting on the waiver wire.
    # Informational only -- retired by D45 (always 0; the wire counts its
    # full hit now). Key kept so cap UI screens don't KeyError.
    waivers_shed = waiver_shed_charge(team)
    buyouts = in_game_buyout_charge(team, season_year)
    s_buyout = seeded_buyout_charge(team)
    s_retained = seeded_retained_charge(team)
    s_overage = seeded_overage_charge(team)
    retained = retained_charge(team)
    try:
        cap = int(getattr(team, "salary_cap", DEFAULT_CAP) or DEFAULT_CAP)
    except Exception:
        cap = DEFAULT_CAP
    total = roster + buyouts + s_buyout + s_retained + s_overage + retained
    return {
        "cap": cap,
        "roster": roster,
        "buried": buried,
        "waivers_shed": waivers_shed,
        "buyouts": buyouts,
        "seeded_buyout": s_buyout,
        "seeded_retained": s_retained,
        "seeded_overage": s_overage,
        "retained": retained,
        "retention_slots": f"{retention_slots_used(team)}/3",
        "dead_cap": buyouts + s_buyout + s_retained + s_overage + retained,
        "total": total,
        "space": cap - total,
        "over_cap": (cap - total) < 0,
        # D46: salary-floor keys. under_floor mirrors over_cap so the
        # day-advance floor gate reads one dict.
        "floor": int(SALARY_CAP_FLOOR),
        "floor_space": total - int(SALARY_CAP_FLOOR),
        "under_floor": total < int(SALARY_CAP_FLOOR),
    }


# ---------------------------------------------------------------------------
# UFA/RFA market scarcity pricing (2026-10-01, Chris's ask)
# ---------------------------------------------------------------------------
# Supply and demand on top of the fixed valuation bands: when the
# free-agent market is thin at a position and many clubs are chasing the
# same gap, asks rise; when the pool is flooded, asks soften. Additive --
# a multiplier into demand_for (default 1.0 = no behavior change), so the
# contract engine itself is untouched. User and AI share it: both ask
# paths (main.py negotiation, ai_team_management._player_ask) funnel
# through demand_for with the same scarcity input.
#
# Tuning (flagged for Chris):
SCARCITY_SLOPE = 0.10        # +10% ask per unit of demand/supply imbalance
SCARCITY_MAX = 1.35          # never more than a 35% scarcity premium
SCARCITY_MIN = 0.90          # never more than a 10% flooded-market discount
SCARCITY_QUALITY_OVR = 78.0  # native scale: only NHL-caliber FAs count as supply
SCARCITY_BID_MIN_SPACE = 2_000_000  # a club needs $2M+ space to be a bidder

# team_needs() codes -> position_group() buckets
_SCARCITY_NEED_TO_GROUP = {
    "C": "Forward", "LW": "Forward", "RW": "Forward",
    "LD": "Defense", "RD": "Defense",
    "G": "Goalie",
}

# Perf: fa_market_scarcity is a pure function of league state but gets called
# dozens of times per day (once per FA candidate per AI team). Cache by
# (league, position group, date) -- the market doesn't move within a day.
# (Muck 2026-10-03: playthrough perf fix)
_SCARCITY_CACHE = {}


def fa_market_scarcity(league, position):
    """Supply/demand read on the free-agent market for one position.

    Returns a dict: multiplier (ask scaling), supply (NHL-caliber FAs in
    the group), demand (clubs with a top-2 need there and $2M+ space),
    and a qualitative signal key for the UI ("thin_market" /
    "high_demand" / "balanced" / "buyers_market"). Pure function of the
    league state -- same answer for user and AI. Never raises.
    """
    out = {"multiplier": 1.0, "supply": 0, "demand": 0,
           "signal": "balanced", "group": ""}
    try:
        group = position_group(position)
    except Exception:
        return out
    out["group"] = group
    # Cache check: same league + group + date = same market.
    try:
        _gm = getattr(league, "game_manager", None)
        _date_key = str(getattr(_gm, "current_date", "") or "")
    except Exception:
        _date_key = ""
    _cache_key = (id(league), group, _date_key)
    _cached = _SCARCITY_CACHE.get(_cache_key)
    if _cached is not None:
        return dict(_cached)
    try:
        pool = list(getattr(league, "free_agents", None) or [])
    except Exception:
        return out
    # --- supply: signable, NHL-caliber FAs in this group -------------------
    supply = 0
    for p in pool:
        try:
            if position_group(getattr(
                    getattr(p, "primary_position", ""), "value",
                    str(getattr(p, "primary_position", "")))) != group:
                continue
            if float(p.overall_rating()) < SCARCITY_QUALITY_OVR:
                continue
            try:
                from draft_generator import player_locked_by_draft as _locked
                if _locked(p):
                    continue  # draft-eligible: not a signable FA
            except Exception:
                pass
            supply += 1
        except Exception:
            continue
    # --- demand: clubs with a top-2 need here and room to bid --------------
    demand = 0
    try:
        from trade_engine import team_needs as _needs
    except Exception:
        _needs = None
    if _needs is not None:
        for team in (getattr(league, "teams", None) or []):
            try:
                needs = _needs(team) or []
                top2 = [_SCARCITY_NEED_TO_GROUP.get(str(n).upper(), "")
                        for n in needs[:2]]
                if group not in top2:
                    continue
                try:
                    space = int(cap_space(team))
                except Exception:
                    space = 0
                if space >= SCARCITY_BID_MIN_SPACE:
                    demand += 1
            except Exception:
                continue
    out["supply"] = supply
    out["demand"] = demand
    if supply == 0 and demand == 0:
        # No market at all (degenerate league / empty pool): no adjustment.
        out["multiplier"] = 1.0
        out["signal"] = "balanced"
        return out
    ratio = float(demand) / max(float(supply), 1.0)
    mult = 1.0 + SCARCITY_SLOPE * (ratio - 1.0)
    mult = max(SCARCITY_MIN, min(SCARCITY_MAX, mult))
    out["multiplier"] = round(mult, 3)
    # --- qualitative signal (UI copy lives in scarcity_signal_text) ---------
    if supply <= 2 and demand >= 3:
        out["signal"] = "thin_market"
    elif mult >= 1.15:
        out["signal"] = "high_demand"
    elif mult <= 0.95:
        out["signal"] = "buyers_market"
    else:
        out["signal"] = "balanced"
    # Store in day-cache before returning.
    try:
        _SCARCITY_CACHE[_cache_key] = dict(out)
        if len(_SCARCITY_CACHE) > 50:
            _oldest = next(iter(_SCARCITY_CACHE))
            del _SCARCITY_CACHE[_oldest]
    except Exception:
        pass
    return out


def scarcity_signal_text(signal, position=None):
    """Qualitative market-demand copy. No numbers -- the analytics stay a
    puzzle; the number should feel earned, never bare."""
    _pos = ""
    try:
        _p = str(position or "").upper()
        _pos = {"C": " at center", "LW": " on the wing",
                "RW": " on the wing", "LD": " on defense",
                "RD": " on defense", "D": " on defense",
                "G": " in goal"}.get(_p, "")
    except Exception:
        pass
    return {
        "thin_market": f"Thin market{_pos} -- few quality options available.",
        "high_demand": f"High demand{_pos} -- several clubs are chasing "
                       f"the same gap.",
        "buyers_market": f"Buyer's market{_pos} -- plenty of options, "
                         f"less competition.",
        "balanced": f"Steady market{_pos}.",
    }.get(signal, f"Steady market{_pos}.")


def scarcity_signal_short(signal) -> str:
    """One-line market-demand label for dense table columns."""
    return {
        "thin_market": "Thin market",
        "high_demand": "High demand",
        "buyers_market": "Buyer's market",
        "balanced": "Steady",
    }.get(signal, "Steady")
