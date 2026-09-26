"""
salary_cap_system.py -- Dynamic NHL salary cap and contract market system.

The cap grows ~2-4% per year (like the real NHL: $83.5M -> $87.7M -> $92M).
Player salary demands are expressed as a percentage of the cap, so when the
cap rises, new contract demands rise with it. Existing contracts are NOT
retroactively changed (like the real NHL).

Market-setting contracts: when a star (85+ OVR on the 1-100 display scale,
i.e. ~42+ on the internal ~50 scale) signs a top-5 AAV deal, it "sets the
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

DEFAULT_CAP = 83_500_000          # 2024-25 NHL cap
MIN_CAP = 70_000_000              # Floor sanity bound
MAX_CAP = 200_000_000             # Ceiling sanity bound
MIN_GROWTH = 0.02                 # 2% minimum annual growth
MAX_GROWTH = 0.04                 # 4% maximum annual growth

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
        cap_sys = SalaryCapSystem()                    # $83.5M default
        cap_sys = SalaryCapSystem(initial_cap=90_000_000)  # user override
        new_cap = cap_sys.advance_cap_year(2025)       # grow for 2025-26
        cap_sys.register_signing("A. Matthews", 13_250_000, ovr=94,
                                 position="C", age=27, season=2025)
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
        Returns the new cap. Growth is 2-4% with randomness, mirroring
        real NHL cap escalation ($83.5M -> $87.7M -> $92M pattern).
        Occasionally (10%) the league has a flat year (0-1% growth)
        like the COVID flat-cap era.
        """
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
