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
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CAP = 104_000_000          # 2026-27 NHL cap (modern day)
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
                   age: int, season: int) -> int:
        """
        Convert a base demand (as cap %) to dollars against the CURRENT cap,
        applying any market-setter premium. This is the single choke point
        for "what does this player ask for" -- all negotiation paths should
        flow through here so demands track the cap.
        """
        premium = self.market_premium(ovr, position, age, season)
        return int(cap_pct_to_dollars(base_cap_pct, self.current_cap)
                   * premium)

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


# Burial exemption (NHL rule): a one-way contract assigned to the minors
# still counts against the cap, minus $1.15M + the league minimum.
# Two-way deals are fully buried -- the minor-league salary never touches
# the NHL cap. Prospects never count.
LEAGUE_MINIMUM_SALARY = 775000
BURY_EXEMPTION = 1150000 + LEAGUE_MINIMUM_SALARY  # $1,925,000


def _on_waiver_wire(p) -> bool:
    """True while a player sits on the waiver wire awaiting clearing."""
    try:
        return bool(getattr(p, "on_waivers", False)) and int(getattr(p, "waiver_days", 0) or 0) > 0
    except Exception:
        return False


def _active_roster_hit(p) -> int:
    """Cap hit of a player on the NHL active roster: full salary.

    Waiver shed: a player on the wire temporarily doesn't count. This
    is the escape valve that lets an over-cap club get compliant via
    waivers (or a shedding trade) and start games. (Real NHL keeps
    counting until assignment; the game sheds on placement by design.)
    When waivers clear, the claim or the burial rule resolves the hit.
    """
    try:
        if _on_waiver_wire(p):
            return 0
        contract = getattr(p, "contract", None)
        if contract is not None:
            hit = int(getattr(contract, "salary", 0) or 0)
            hit -= int(getattr(p, "retained_amount", 0) or 0)
            return max(0, hit)
    except Exception:
        pass
    return 0


def minor_league_cap_charge(p) -> int:
    """Cap hit of a player under NHL contract assigned to the minors.

    True NHL rule: two-way deals count $0 (minor-league salary is cap
    exempt); one-way deals count salary minus the burial exemption.
    A player on the waiver wire is fully shed until waivers clear.
    """
    try:
        if _on_waiver_wire(p):
            return 0
        contract = getattr(p, "contract", None)
        if contract is None:
            return 0
        if bool(getattr(contract, "two_way", False)):
            return 0
        hit = int(getattr(contract, "salary", 0) or 0)
        hit -= int(getattr(p, "retained_amount", 0) or 0)
        return max(0, hit - BURY_EXEMPTION)
    except Exception:
        return 0


def roster_cap_charge(team) -> int:
    """Active-roster cap charge under the true NHL rule (Eastside logic).

    Only the NHL active roster counts at full salary. Prospects never
    count. Players under NHL contract in the minors follow the burial
    rule: two-way deals are fully exempt, one-way deals count salary
    minus the $1.925M burial exemption.

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

    A waived player doesn't count until waivers clear -- the escape
    valve that lets an over-cap club get compliant and start games.
    """
    try:
        return sum(
            max(0, int(getattr(getattr(p, "contract", None), "salary", 0) or 0)
                - int(getattr(p, "retained_amount", 0) or 0))
            for p in (getattr(team, "roster", None) or [])
            if _on_waiver_wire(p))
    except Exception:
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
    # Informational only -- already excluded from the roster charge above.
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
    }
