"""Real-world NHL dead-cap data for the 2026-27 season.

Dead cap = buyout cap hits + retained salary + bonus-overage carryovers.
These are the PRE-EXISTING real-life penalties each club carries into a new
2026-27 game, so every team starts with finances that mirror modern-day
reality (cap upper limit $104M).

Research: 2026-09-28. Primary source: PuckPedia team pages (2026-27 column).
Cross-check: Pro Hockey Rumors 2026-27 Salary Cap Deep Dive series and
Daily Faceoff. Full per-team notes live in deadcap_2026_27_reference.md.

Normalizations (excluded for consistency):
- Performance-bonus cushion rows (not dead cap).
- Season-opening IR charges ($10K-$110K).
- Buried-player AHL burial excess.

Scope note: these are OPENING-DAY 2026-27 figures. Buyout hits change
year to year in real life and the research did not capture full multi-year
schedules, so seeded penalties apply to the 2026-27 season only. At the
first season rollover they expire; from then on the game's own buyout /
retention / bonus systems generate dead cap organically. In-game buyouts,
retained salary from trades, and bonus overages are NEVER touched by the
"start without cap penalties" toggle -- it only clears these seeded
real-life penalties.
"""

# team name -> (buyout $, retained $, bonus-overage $) for 2026-27
DEAD_CAP_2026_27 = {
    # Atlantic
    "Boston Bruins": (0, 615_000, 0),          # Carlo retention thru 2026-27
    "Buffalo Sabres": (6_444_000, 0, 0),       # Skinner buyout thru 2028-29
    "Detroit Red Wings": (0, 0, 0),
    "Florida Panthers": (0, 0, 150_000),       # bonus carryover
    "Montreal Canadiens": (0, 3_250_000, 1_934_000),  # Gallagher retention + carryover
    "Ottawa Senators": (875_000, 1_000_000, 0),      # White buyout; Korpisalo retention
    "Tampa Bay Lightning": (0, 0, 0),
    "Toronto Maple Leafs": (0, 0, 0),
    # Metropolitan
    "Carolina Hurricanes": (0, 0, 0),
    "Columbus Blue Jackets": (0, 0, 0),
    "New Jersey Devils": (0, 0, 1_250_000),    # bonus carryover
    "New York Islanders": (0, 0, 3_500_000),   # bonus carryover
    "New York Rangers": (0, 0, 0),
    "Philadelphia Flyers": (0, 1_200_000, 0),  # Hathaway retained, final year
    "Pittsburgh Penguins": (0, 500_000, 0),    # Wotherspoon retained, 2026-27 only
    "Washington Capitals": (0, 0, 0),
    # Central
    "Chicago Blackhawks": (258_000, 2_500_000, 0),  # Brodie buyout; Jones retention
    "Colorado Avalanche": (0, 0, 2_292_000),   # bonus carryover
    "Dallas Stars": (0, 0, 2_080_000),         # bonus carryover
    "Minnesota Wild": (1_667_000, 0, 0),       # Parise + Suter 833K each
    "Nashville Predators": (3_556_000, 0, 0),  # Turris 2M; Duchene 1.556M
    "St. Louis Blues": (1_333_000, 0, 0),      # Drouin buyout thru 2027-28
    "Utah Mammoth": (650_000, 0, 0),           # Ekman-Larsson buyout thru 2029-30
    "Winnipeg Jets": (0, 0, 0),
    # Pacific
    "Anaheim Ducks": (0, 0, 0),
    "Calgary Flames": (0, 3_850_000, 0),       # Coleman 2.45M; Kadri 1.4M
    "Edmonton Oilers": (2_600_000, 0, 250_000),  # Campbell buyout + carryover
    "Los Angeles Kings": (600_000, 0, 0),      # Richards recapture/buyout
    "San Jose Sharks": (2_833_000, 2_888_000, 814_000),  # Jones+Vlasic; Karlsson+Hertl; carryover
    "Seattle Kraken": (379_000, 0, 0),         # Veleno buyout, final year
    "Vancouver Canucks": (4_767_000, 1_500_000, 0),  # OEL buyout + retained
    "Vegas Golden Knights": (0, 0, 0),
}

SEASON = 2026  # the season these figures describe (2026-27)

# Real-world projected 2026-27 cap space per club (cap $104M), in dollars.
# Research: 2026-09-28. Source: PuckPedia 2026-27 team cap table
# (https://puckpedia.com/e/teams), "Proj. Space" column.
#
# Used at league generation so day-one cap situations mirror real life:
# capped-out contenders (Vegas, New Jersey, Edmonton...) start tight and
# cap-flush clubs (Detroit, Seattle, Vancouver...) start with room to
# weaponize. Negative-space clubs (Toronto, Florida, Columbus, Vegas)
# are clamped to MIN_TARGET_ROOM at use time -- real clubs operate over
# the cap via LTIR, but the game needs day-one compliance, so they
# start in an LTIR-equivalent squeeze instead of over the cap.
CAP_ROOM_2026_27 = {
    # Atlantic
    "Boston Bruins": 6_047_000,
    "Buffalo Sabres": 1_583_000,
    "Detroit Red Wings": 18_613_000,
    "Florida Panthers": -871_000,
    "Montreal Canadiens": 1_891_000,
    "Ottawa Senators": 2_458_000,
    "Tampa Bay Lightning": 1_903_000,
    "Toronto Maple Leafs": -3_808_000,
    # Metropolitan
    "Carolina Hurricanes": 8_427_000,
    "Columbus Blue Jackets": -35_000,
    "New Jersey Devils": 52_000,
    "New York Islanders": 2_749_000,
    "New York Rangers": 468_000,
    "Philadelphia Flyers": 13_095_000,
    "Pittsburgh Penguins": 7_128_000,
    "Washington Capitals": 125_000,
    # Central
    "Chicago Blackhawks": 1_452_000,
    "Colorado Avalanche": 150_000,
    "Dallas Stars": 303_000,
    "Minnesota Wild": 1_153_000,
    "Nashville Predators": 11_991_000,
    "St. Louis Blues": 2_832_000,
    "Utah Mammoth": 4_837_000,
    "Winnipeg Jets": 12_406_000,
    # Pacific
    "Anaheim Ducks": 185_000,
    "Calgary Flames": 13_908_000,
    "Edmonton Oilers": 228_000,
    "Los Angeles Kings": 1_800_000,
    "San Jose Sharks": 2_706_000,
    "Seattle Kraken": 16_997_000,
    "Vancouver Canucks": 15_925_000,
    "Vegas Golden Knights": -8_824_000,
}

# Floor for a club's day-one target room. Over-cap real-life clubs are
# clamped here (LTIR-equivalent squeeze, never a day-one violation).
MIN_TARGET_ROOM = 500_000


def target_cap_room(team_name: str) -> int:
    """Day-one target cap room for a club, in dollars.

    Real 2026-27 projected space, canonicalized through TEAM_ALIASES,
    clamped to MIN_TARGET_ROOM so no club starts over the cap.
    Unknown teams default to a $1M operating cushion.
    """
    key = _team_key(team_name)
    room = CAP_ROOM_2026_27.get(key)
    if room is None:
        return 1_000_000
    return max(MIN_TARGET_ROOM, room)

# Alternate spellings / short names seen across the codebase's generators.
TEAM_ALIASES = {
    "Buffalo Sabres": ("Buffalo Sabres",),
    "Montreal Canadiens": ("Montreal Canadiens", "Montréal Canadiens"),
    "New York Islanders": ("New York Islanders", "NY Islanders"),
    "New York Rangers": ("New York Rangers", "NY Rangers"),
    "Vancouver Canucks": ("Vancouver Canucks",),
    "San Jose Sharks": ("San Jose Sharks", "San Jose"),
    "Utah Mammoth": ("Utah Mammoth", "Utah Hockey Club", "Utah"),
}


def _team_key(team) -> str:
    """Best-effort canonical name for a Team object (or a team-name string)."""
    if isinstance(team, str):
        name = team.strip()
    else:
        name = getattr(team, "team_name", "") or ""
        name = name.strip()
    if name in DEAD_CAP_2026_27:
        return name
    # Try city + team_name combos and aliases
    city = (getattr(team, "city", "") or "").strip()
    combo = f"{city} {name}".strip()
    if combo in DEAD_CAP_2026_27:
        return combo
    for canonical, aliases in TEAM_ALIASES.items():
        if name in aliases or combo in aliases:
            return canonical
    return name


def get_dead_cap(team_name: str):
    """Return (buyout, retained, overage) for a team name, or (0, 0, 0)."""
    return DEAD_CAP_2026_27.get((team_name or "").strip(), (0, 0, 0))


def total_dead_cap(team_name: str) -> int:
    b, r, o = get_dead_cap(team_name)
    return b + r + o


def should_seed_dead_cap(season_year: int, settings) -> bool:
    """Whether a new game should seed real-life dead-cap penalties.

    Cap rules always apply; cap penalties are skipped when the user chose
    "start without cap penalties" or starts with a fantasy draft (even
    playing field -- every club begins at $0 dead cap while the $104M
    ceiling still governs the league).
    """
    settings = settings or {}
    if settings.get('start_without_cap_penalties', False):
        return False
    if settings.get('fantasy_draft', False):
        return False
    return season_year == SEASON


def seed_real_dead_cap(league, overwrite: bool = False) -> int:
    """Seed 2026-27 real-life dead-cap penalties onto every league team.

    Sets three plain attributes per team (old-save safe, additive):
      team.real_buyout_cap, team.real_retained_salary, team.real_bonus_overage
    plus team.real_dead_cap_seeded = True.

    In-game buyout_cap_hits are never touched. Returns the number of teams
    seeded. Idempotent unless overwrite=True.
    """
    teams = getattr(league, "teams", []) or []
    seeded = 0
    for team in teams:
        if getattr(team, "real_dead_cap_seeded", False) and not overwrite:
            continue
        buyout, retained, overage = get_dead_cap(_team_key(team))
        team.real_buyout_cap = int(buyout)
        team.real_retained_salary = int(retained)
        team.real_bonus_overage = int(overage)
        team.real_dead_cap_season = SEASON
        team.real_dead_cap_seeded = True
        seeded += 1
    return seeded


def clear_dead_cap(league) -> int:
    """Clear seeded real-life dead-cap penalties ("start without cap penalties").

    Only clears the seeded real_* attributes. In-game buyout_cap_hits,
    trade-retained salary, and bonus overages earned during play are
    untouched. Returns the number of teams cleared.
    """
    teams = getattr(league, "teams", []) or []
    cleared = 0
    for team in teams:
        if not getattr(team, "real_dead_cap_seeded", False):
            # Still zero the attributes defensively so no stale values linger.
            team.real_buyout_cap = 0
            team.real_retained_salary = 0
            team.real_bonus_overage = 0
            continue
        team.real_buyout_cap = 0
        team.real_retained_salary = 0
        team.real_bonus_overage = 0
        team.real_dead_cap_seeded = False
        cleared += 1
    return cleared


def expire_seeded_dead_cap(league, season_year: int) -> int:
    """Expire seeded penalties once the league moves past the 2026-27 season.

    Called on season rollover. From 2027-28 on, the game's own buyout /
    retention / bonus systems own dead cap. Returns teams expired.
    """
    if season_year <= SEASON:
        return 0
    teams = getattr(league, "teams", []) or []
    expired = 0
    for team in teams:
        if getattr(team, "real_dead_cap_seeded", False):
            team.real_buyout_cap = 0
            team.real_retained_salary = 0
            team.real_bonus_overage = 0
            team.real_dead_cap_seeded = False
            expired += 1
    return expired


def seeded_dead_cap_total(team) -> int:
    """Current seeded real-life dead-cap total for a team (0 if none)."""
    return (int(getattr(team, "real_buyout_cap", 0) or 0)
            + int(getattr(team, "real_retained_salary", 0) or 0)
            + int(getattr(team, "real_bonus_overage", 0) or 0))
