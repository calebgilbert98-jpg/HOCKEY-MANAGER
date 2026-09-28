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

# Real NHL retained-salary rules (additive; the engine never had them).
MAX_RETENTION_SLOTS = 3   # max active retained-salary transactions per club
MAX_RETENTION_PCT = 50    # max percent of the cap hit one club may retain

# ---------------------------------------------------------------------------
# No-trade / no-movement clauses + waiver decisions
# ---------------------------------------------------------------------------
# Real NHL trade protection, seeded from real_ntc_data.py on new 2026-27
# games: full NMCs (block trades AND waivers/AHL assignment), full NTCs
# (block all trades), and modified NTCs (the player holds a no-trade or
# approved list of N teams). A player with a clause must be asked to waive
# it for a specific destination; his answer depends on his personality,
# his team's situation and performance, and his happiness -- never on a
# bare coin flip. Additive: players without clauses behave exactly as
# before.


def clause_of(player):
    """Return (kind, detail) for a player's trade protection.

    kind is "NMC", "NTC", "M-NTC", or None. detail is a short human label
    like "full no-movement clause" or "10-team no-trade list".
    """
    try:
        c = getattr(player, "contract", None)
        if c is None:
            return None, ""
        if bool(getattr(c, "no_movement_clause", False)):
            n = int(getattr(c, "modified_ntc_teams", 0) or 0)
            d = "full no-movement clause" + (f" ({n}-team list)" if n else "")
            return "NMC", d
        # A list size on the contract means modified NTC, even though the
        # underlying flag is the same no-trade bit -- check it first.
        n = int(getattr(c, "modified_ntc_teams", 0) or 0)
        if n > 0:
            if bool(getattr(c, "modified_ntc_approved", False)):
                return "M-NTC", f"{n}-team approved list"
            return "M-NTC", f"{n}-team no-trade list"
        if bool(getattr(c, "no_trade_clause", False)):
            return "NTC", "full no-trade clause"
    except Exception:
        pass
    return None, ""


def clause_tag(player):
    """Short badge for trade-screen asset rows: NMC / NTC / M-NTC / ''."""
    kind, _detail = clause_of(player)
    return kind or ""


def _team_points_pct(team, league=None):
    """Team's points percentage from league standings (0..1, 0.5 default)."""
    try:
        name = getattr(team, "team_name", team)
        st = (getattr(league, "standings", {}) or {}).get(name, {})
        w = float(st.get("W", 0) or 0)
        l = float(st.get("L", 0) or 0)
        otl = float(st.get("OTL", 0) or 0)
        gp = w + l + otl
        if gp > 0:
            return (w * 2 + otl) / (gp * 2)
    except Exception:
        pass
    try:  # fallback: raw points/games attributes
        pts = float(getattr(team, "points", 0) or 0)
        gp = float(getattr(team, "games_played", 0) or 0)
        if gp > 0:
            return pts / (gp * 2)
    except Exception:
        pass
    return 0.5


def _season_year(league) -> int:
    """Current league year for season-fixed mechanics (M-NTC lists)."""
    try:
        return int(getattr(league, "season_year", 0) or 0)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Dynamic M-NTC list engine: what puts a team on a player's no-trade list.
#
# Real no-trade lists aren't random -- they're built from a player's
# circumstances. Four factors drive the model:
#   * Hometown: players want to be near home (same state/province is a
#     strong pull; some prefer to stay in their home country).
#   * Taxes: the smallest factor by far. No-income-tax markets
#     (FL/TX/NV/TN/WA) nudge slightly; high-tax markets (CA/NY/QC/ON/...)
#     nudge slightly the other way -- and only for players not making
#     major dollars. Stars barely notice; role players feel the bite.
#   * Team situation: veterans chasing Cups block rebuilders; prime-age
#     players lean toward contenders; youngsters care less about winning.
#   * Circumstantial opportunity: a young player blocks clubs that are
#     stacked at his position (no ice time); a star welcomes a club
#     where he'd be the guy.
# The factors feed a per-(player, destination, season) block probability.
# The list stays season-fixed and deterministic (hash, not re-rollable),
# but its *membership* now reflects the player's situation instead of a
# flat league-wide estimate.
# ---------------------------------------------------------------------------

# team_name -> (region code, country, tax tier). Tax tiers reflect real
# top-marginal income-tax reality: "none" = no state/provincial income tax.
_TEAM_LOCALE = {
    # Metropolitan
    "Carolina Hurricanes": ("NC", "USA", "low"),
    "Columbus Blue Jackets": ("OH", "USA", "low"),
    "New Jersey Devils": ("NJ", "USA", "high"),
    "New York Islanders": ("NY", "USA", "high"),
    "New York Rangers": ("NY", "USA", "high"),
    "Philadelphia Flyers": ("PA", "USA", "low"),
    "Pittsburgh Penguins": ("PA", "USA", "low"),
    "Washington Capitals": ("DC", "USA", "mid"),
    # Atlantic
    "Boston Bruins": ("MA", "USA", "mid"),
    "Buffalo Sabres": ("NY", "USA", "high"),
    "Detroit Red Wings": ("MI", "USA", "low"),
    "Florida Panthers": ("FL", "USA", "none"),
    "Montréal Canadiens": ("QC", "Canada", "high"),
    "Ottawa Senators": ("ON", "Canada", "high"),
    "Tampa Bay Lightning": ("FL", "USA", "none"),
    "Toronto Maple Leafs": ("ON", "Canada", "high"),
    # Central
    "Chicago Blackhawks": ("IL", "USA", "low"),
    "Colorado Avalanche": ("CO", "USA", "low"),
    "Dallas Stars": ("TX", "USA", "none"),
    "Minnesota Wild": ("MN", "USA", "mid"),
    "Nashville Predators": ("TN", "USA", "none"),
    "St. Louis Blues": ("MO", "USA", "low"),
    "Utah Hockey Club": ("UT", "USA", "low"),
    "Winnipeg Jets": ("MB", "Canada", "mid"),
    # Pacific
    "Anaheim Ducks": ("CA", "USA", "high"),
    "Calgary Flames": ("AB", "Canada", "low"),
    "Edmonton Oilers": ("AB", "Canada", "low"),
    "Los Angeles Kings": ("CA", "USA", "high"),
    "San Jose Sharks": ("CA", "USA", "high"),
    "Seattle Kraken": ("WA", "USA", "none"),
    "Vancouver Canucks": ("BC", "Canada", "high"),
    "Vegas Golden Knights": ("NV", "USA", "none"),
}

_CANADA_REGIONS = {"ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL",
                   "PE", "NT", "YT", "NU"}
_USA_REGIONS = {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
                "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
                "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
                "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
                "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI",
                "WY"}
# Country name -> (region code, country) for birthplaces without a region
# ("Stockholm") -- falls back to the player's nationality first.
_BIRTH_COUNTRY_REGION = {
    "sweden": ("SE", "Sweden"), "finland": ("FI", "Finland"),
    "russia": ("RU", "Russia"), "czech": ("CZ", "Czechia"),
    "czechia": ("CZ", "Czechia"), "slovakia": ("SK", "Slovakia"),
    "germany": ("DE", "Germany"), "switzerland": ("CH", "Switzerland"),
    "austria": ("AT", "Austria"), "norway": ("NO", "Norway"),
    "denmark": ("DK", "Denmark"), "latvia": ("LV", "Latvia"),
    "belarus": ("BY", "Belarus"), "ukraine": ("UA", "Ukraine"),
    "kazakhstan": ("KZ", "Kazakhstan"),
}


def _team_locale(team):
    """(region, country, tax_tier) for a team; ("", "", "mid") unknown."""
    try:
        name = getattr(team, "team_name", str(team))
        return _TEAM_LOCALE.get(name, ("", "", "mid"))
    except Exception:
        return ("", "", "mid")


def _birth_locale(player):
    """(region, country) parsed from birthplace + nationality.

    "Toronto, ON" -> ("ON", "Canada"); "Boston, MA" -> ("MA", "USA");
    "Stockholm" -> ("SE", "Sweden") via nationality/country lookup.
    Returns ("", "") when nothing is known.
    """
    try:
        bp = str(getattr(player, "birthplace", "") or "").strip()
        nat = str(getattr(player, "nationality", "") or "").strip()
    except Exception:
        return "", ""
    region, country = "", ""
    if "," in bp:
        _city, _, tail = bp.rpartition(",")
        code = tail.strip().upper()
        if code in _CANADA_REGIONS:
            region, country = code, "Canada"
        elif code in _USA_REGIONS:
            region, country = code, "USA"
    if not country:
        # No region code: identify the country from the birthplace text or
        # the player's nationality ("Sweden" -> SE).
        low = (bp + " " + nat).lower()
        for cname, (rcode, cfull) in _BIRTH_COUNTRY_REGION.items():
            if cname in low:
                region, country = rcode, cfull
                break
        else:
            if "canada" in low:
                country = "Canada"
            elif "usa" in low or "united states" in low or \
                    "america" in low:
                country = "USA"
    return region, country


def _hometown_factor(player, to_team):
    """Multiplier + note: players avoid blocking teams near home."""
    try:
        pregion, pcountry = _birth_locale(player)
        tregion, tcountry, _tax = _team_locale(to_team)
    except Exception:
        return 1.0, ""
    if not pcountry or not tcountry:
        return 1.0, ""
    if pregion and pregion == tregion:
        return 0.25, "close to home"
    if pcountry.lower() == tcountry.lower():
        return 0.85, ""
    return 1.10, ""


def _tax_salience(player):
    """How much taxes matter to this player: 1.0 for role players, fading
    to 0.25 for stars on major dollars. A $1.5M player feels the bite of
    a high-tax market; an $11M star barely notices."""
    try:
        salary = float(getattr(getattr(player, "contract", None),
                               "salary", 0) or 0)
    except Exception:
        return 1.0
    if salary <= 2_000_000:
        return 1.0
    if salary >= 10_000_000:
        return 0.25
    return 1.0 - 0.75 * (salary - 2_000_000) / 8_000_000


def _tax_factor(player, to_team):
    """Multiplier + note: taxes are the smallest list factor by far, and
    salary-scaled -- they nudge role players, not stars."""
    _region, _country, tier = _team_locale(to_team)
    w = _tax_salience(player)
    base = {"none": 0.90, "low": 0.95, "mid": 1.0, "high": 1.08}.get(tier, 1.0)
    mult = 1.0 + (base - 1.0) * w
    note = ""
    if w > 0.5:
        if tier == "none":
            note = "no state income tax"
        elif tier == "high":
            note = "a high-tax market"
    return mult, note


def _situation_factor(player, to_team, league):
    """Multiplier + note: contention matters most to veterans."""
    try:
        age = int(getattr(player, "age", 28) or 28)
        to_pct = _team_points_pct(to_team, league)
    except Exception:
        return 1.0, ""
    if age >= 33:
        if to_pct < 0.45:
            return 1.55, "rebuilding while he's chasing a Cup"
        if to_pct > 0.62:
            return 0.70, "a contender"
    elif age > 25:
        if to_pct < 0.45:
            return 1.25, ""
        if to_pct > 0.62:
            return 0.85, ""
    # 25 and under: winning matters less than playing time (see the
    # opportunity factor below).
    return 1.0, ""


def _position_group(player):
    """'F', 'D', or 'G' for a player."""
    try:
        from game_classes import PlayerPosition as _PP
        pos = getattr(player, "primary_position", None)
        if pos == _PP.GOALIE:
            return "G"
        if pos in (_PP.LEFT_DEFENSE, _PP.RIGHT_DEFENSE, _PP.DEFENSE):
            return "D"
        return "F"
    except Exception:
        return "F"


def _opportunity_factor(player, to_team):
    """Multiplier + note: is there actually ice time for him there?

    Counts destination roster players in his position group playing at
    (or above) his level. Young players block buried depth charts;
    established stars welcome a club where they'd be the guy.
    """
    try:
        group = _position_group(player)
        age = int(getattr(player, "age", 28) or 28)
        mine = float(player.overall_rating())
        mates = [p for p in (getattr(to_team, "roster", None) or [])
                 if _position_group(p) == group]
    except Exception:
        return 1.0, ""
    try:
        if group == "G":
            if age <= 28 and len(mates) >= 2:
                return 1.50, "they're deep in net"
            if len(mates) <= 1:
                return 0.75, "he'd own the crease there"
            return 1.0, ""
        ahead = sum(1 for m in mates
                    if float(m.overall_rating()) >= mine - 5)
        if age <= 27 and ahead >= 6:
            return 1.45, "buried on their depth chart"
        if ahead <= 1:
            return 0.80, "he'd play big minutes there"
    except Exception:
        pass
    return 1.0, ""


def _mntc_block_probability(player, to_team, league=None):
    """Probability (0.05..0.92) this destination sits on the player's
    no-trade list, from hometown, taxes, team situation and opportunity.
    Returns (p, notes) -- notes name the factors that moved the needle.
    """
    c = getattr(player, "contract", None)
    n = int(getattr(c, "modified_ntc_teams", 0) or 0) if c is not None else 0
    base = max(0.01, min(0.99, n / 31.0))
    notes = []
    p = base
    for factor in (_hometown_factor(player, to_team),
                   _tax_factor(player, to_team),
                   _situation_factor(player, to_team, league),
                   _opportunity_factor(player, to_team)):
        try:
            mult, note = factor[0], factor[1]
        except Exception:
            continue
        p *= mult
        if note and mult != 1.0:
            notes.append(note)
    return max(0.05, min(0.92, p)), notes, base


def mntc_list_teams(player, league, n=None, exclude=None):
    """Materialize the player's dynamic no-trade list: the n teams with
    the highest block probability (deterministic; season-fixed).

    exclude: team name (or team) left off the list -- normally his own
    club. Returns a list of team names, longest-blocked first.
    """
    try:
        c = getattr(player, "contract", None)
        n = int(n if n is not None
                else getattr(c, "modified_ntc_teams", 0) or 0)
    except Exception:
        n = 0
    if n <= 0:
        return []
    try:
        excl = getattr(exclude, "team_name", exclude)
        teams = [t for t in (getattr(league, "teams", None) or [])
                 if getattr(t, "team_name", t) != excl]
    except Exception:
        return []
    scored = []
    for t in teams:
        try:
            p, _notes, _base = _mntc_block_probability(player, t, league)
        except Exception:
            continue
        scored.append((p, str(getattr(t, "team_name", t))))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [name for _p, name in scored[:n]]


def _mntc_blocks(player, to_team, league=None):
    """Does his modified no-trade clause actually block THIS destination?

    Real M-NTCs are season-fixed submitted lists -- the same answer all
    year, refreshed at the season's start. The list itself is private (as
    in real life): when it isn't explicitly known, membership is derived
    deterministically from (player, destination, season), so there is no
    re-roll exploit -- asking twice can't change the answer. The chance a
    destination sits on the list comes from the dynamic list engine
    (hometown, taxes, team situation, opportunity), not a flat estimate.
    When his agent names a team, the GM learns it and it is recorded on
    the contract's no_trade_list.

    Returns (blocked: bool, reason: str).
    """
    c = getattr(player, "contract", None)
    name = getattr(player, "full_name", str(player))
    n = int(getattr(c, "modified_ntc_teams", 0) or 0) if c is not None else 0
    if n <= 0:
        return False, "no list on file"
    to_name = getattr(to_team, "team_name", str(to_team))
    norm = str(to_name).strip().lower()
    try:
        known = [str(t).strip() for t in (getattr(c, "no_trade_list", []) or [])]
    except Exception:
        known = []
    for b in known:
        bl = b.lower()
        if norm and (norm == bl or norm in bl or bl in norm):
            return True, f"{to_name} is on {name}'s {n}-team no-trade list"
    approved = bool(getattr(c, "modified_ntc_approved", False)) if c is not None else False
    if n >= 31 and not approved:
        return True, f"his {n}-team list covers the whole league"
    # Private list: deterministic per (player, destination, season) --
    # the membership chance comes from the dynamic list engine (hometown,
    # taxes, team situation, opportunity), so the list reads like a real
    # player's submitted list instead of a flat league-wide estimate.
    import hashlib as _hl
    season = _season_year(league)
    pid = str(getattr(player, "id", "") or "")
    digest = _hl.sha256(f"{pid}|{to_name}|{season}".encode()).hexdigest()
    u = int(digest[:8], 16) / 0xFFFFFFFF
    try:
        p, notes, base = _mntc_block_probability(player, to_team, league)
    except Exception:
        p, notes, base = max(0.05, min(0.9, n / 31.0)), [], n / 31.0
    if approved:
        # Approved list: only n teams are acceptable. Desirable teams
        # (low block probability) land on it more often -- the inverse of
        # the block model: p_accept = base * (base / p).
        p_accept = max(0.03, min(0.97, base * (base / max(0.01, p))))
        if u < p_accept:
            return False, f"{to_name} made his {n}-team approved list"
        return True, f"{to_name} isn't on {name}'s {n}-team approved list"
    if u < p:
        try:
            c.no_trade_list.append(to_name)  # his agent named them: learned
        except Exception:
            pass
        why = f"{to_name} is on {name}'s {n}-team no-trade list"
        if notes:
            why += f" ({'; '.join(notes[:2])})"
        return True, why
    return False, f"{to_name} isn't on {name}'s {n}-team no-trade list"


def will_waive_ntc(player, from_team, to_team=None, league=None, rng=None,
                   context="trade"):
    """Would the player waive his clause for from_team -> to_team?

    Decided by personality (loyalty, controversy, age/cup-chase), team
    situation and performance (points pace of both clubs), and happiness --
    never a bare coin flip. Returns (bool, reason).

    context="trade" (default) or "waivers": an NMC also blocks waiver
    placement, so a GM can ask for consent to expose him -- the
    destination is then the league-average claimant.
    """
    import random as _random
    rng = rng or _random
    name = getattr(player, "full_name", str(player))
    kind, detail = clause_of(player)
    if kind is None:
        return True, f"{name} has no clause to waive."
    from_name = getattr(from_team, "team_name", str(from_team))
    if context == "waivers":
        # NMC consent for a waiver placement: the claimant is unknown, so
        # the player judges it as exposure to a league-average club.
        to_team = None
        to_name = "the waiver wire"
    else:
        to_name = getattr(to_team, "team_name", str(to_team))

    # Modified NTC: the clause only bites when THIS destination is on his
    # season-fixed list. Off the list, no waiver is needed at all.
    _explicit_list = False
    if kind == "M-NTC":
        _blocked, _why = _mntc_blocks(player, to_team, league)
        if not _blocked:
            return True, f"{name}'s {detail} doesn't block this move -- {_why}."
        notes_head = f"he'd have to make an exception: {_why}"
        # Naming the team outright is a much harder no than landing on the
        # private list by chance.
        try:
            _known = [str(t).strip().lower()
                      for t in (player.contract.no_trade_list or [])]
            _tnorm = str(to_name).strip().lower()
            _explicit_list = bool(_tnorm) and any(
                _tnorm == b or _tnorm in b or b in _tnorm for b in _known)
        except Exception:
            _explicit_list = False

    score = 45.0
    notes = []
    if kind == "M-NTC":
        # Set above: he's on the list, so this waiver asks for an exception.
        notes.append(notes_head)

    # -- Happiness: unhappy players want out, happy ones stay put.
    happiness = float(getattr(player, "happiness", 70) or 70)
    if happiness < 40:
        score += 22
        notes.append("he's unhappy here and wants a fresh start")
    elif happiness < 55:
        score += 8
    elif happiness > 78:
        score -= 16
        notes.append("he's happy here")
    morale = float(getattr(player, "morale", 70) or 70)
    if morale < 35:
        score += 6
    elif morale > 80:
        score -= 5

    # -- Team situation + performance: players chase winning.
    from_pct = _team_points_pct(from_team, league)
    to_pct = _team_points_pct(to_team, league)
    diff = to_pct - from_pct
    score += diff * 70
    if diff > 0.12:
        notes.append(f"the {to_name} are contending while the {from_name} struggle")
    elif diff < -0.12:
        notes.append("he'd be leaving a contender for a worse team")

    # -- Personality: loyalty anchors, controversy loosens, age chases cups.
    try:
        from reputation_system import contract_loyalty
        loyalty = float(contract_loyalty(player))  # 0..1
    except Exception:
        loyalty = 0.5
    score -= (loyalty - 0.5) * 40
    if loyalty > 0.75:
        notes.append("he's fiercely loyal to the club")
    controversy = float(getattr(player, "controversy", 0) or 0)
    if controversy > 70:
        score += 8
        notes.append("he's never been afraid of a change of scenery")
    age = int(getattr(player, "age", 28) or 28)
    if age >= 33 and diff > 0.06:
        score += 18
        notes.append(f"at {age}, he's chasing a Cup before time runs out")
    elif age <= 24 and diff < -0.05:
        score -= 8
        notes.append("he'd rather develop with a winner")

    # -- Destination pull: taxes and home shape a waiver the same way
    # they shape the list itself. Taxes are a small nudge, and only for
    # players not on major dollars.
    if to_team is not None:
        try:
            _tr, _tc, _tier = _team_locale(to_team)
            _w = _tax_salience(player)
            if _tier == "none":
                score += 3.0 * _w
                if _w > 0.5:
                    notes.append("there's no state income tax there")
            elif _tier == "high":
                score -= 2.5 * _w
                if _w > 0.5:
                    notes.append("the tax bite there is brutal")
            _pr, _pc = _birth_locale(player)
            if _pr and _pr == _tr:
                score += 10
                notes.append("it's close to home")
            elif _pc and _tc and _pc.lower() != _tc.lower():
                score -= 4
                notes.append("it's across the border from home")
        except Exception:
            pass

    # -- Clause strength: NMCs are the hardest to move.
    if kind == "NMC":
        score -= 18
        notes.append("a full no-movement clause is the hardest to waive")
    elif kind == "M-NTC":
        # List membership was settled above (season-fixed): a blocked
        # destination now just needs him willing to make an exception.
        score += 4
        if _explicit_list:
            score -= 45
            notes.append("he specifically put them on his no-trade list")

    waives = rng.random() * 100 < max(5, min(95, score))
    _verb = "waives" if waives else "refuses to waive"
    if context == "waivers":
        why = f"{name} {_verb} his {detail} for a waiver placement"
    else:
        why = f"{name} {_verb} his {detail}"
    if notes:
        why += " -- " + "; ".join(notes[:2])
    why += "."
    return waives, why


def trade_vetoes(from_team, to_team, assets, league=None):
    """Clause vetoes blocking from_team -> to_team for these assets.

    Returns a list of {"player", "clause", "detail"} for players whose
    NTC/NMC/M-NTC blocks the move. Players who already waived for this
    destination (contract.ntc_waiver_for) are skipped. Picks never veto.

    A modified NTC only vetoes when THIS destination is actually on the
    player's season-fixed list -- off the list, the clause doesn't bite.
    """
    to_name = getattr(to_team, "team_name", str(to_team))
    vetoes = []
    for a in assets or []:
        if _is_pick(a):
            continue
        kind, detail = clause_of(a)
        if kind is None:
            continue
        try:
            if str(getattr(a.contract, "ntc_waiver_for", "") or "") == to_name:
                continue
        except Exception:
            pass
        if kind == "M-NTC":
            blocked, why = _mntc_blocks(a, to_team, league)
            if not blocked:
                continue
            detail = f"{detail} ({why})"
        vetoes.append({"player": a, "clause": kind, "detail": detail})
    return vetoes


def protection_label(prot: str) -> str:
    """Human label for a pick-protection code ('top-10' -> 'Top-10 protected')."""
    return {"top-3": "Top-3 protected",
            "top-10": "Top-10 protected",
            "lottery": "Lottery protected"}.get(prot or "", "")


def retention_slots_used(team) -> int:
    """Active retained-salary transactions on a club (NHL max is 3)."""
    try:
        from salary_cap_system import retention_slots_used as _rsu
        return _rsu(team)
    except Exception:
        return 0


def _retention_check(retaining_team, player, pct, extra=None):
    """Shared retention validation. Returns (ok, amount, reason).

    extra: {player_id: pct} other PROPOSED retentions in the same deal --
    they consume slots too, so the UI can validate the whole package.
    """
    try:
        pct = float(pct or 0)
    except Exception:
        return False, 0, "Retention must be a number."
    if pct <= 0 or pct > MAX_RETENTION_PCT:
        return False, 0, f"Retention must be 1-{MAX_RETENTION_PCT}%."
    contract = getattr(player, "contract", None)
    salary = int(getattr(contract, "salary", 0) or 0) if contract else 0
    if salary <= 0:
        return False, 0, "That player has no cap hit to retain."
    # Slot count: active ledger entries + other proposed terms (distinct
    # players), minus this player if he already holds a slot.
    try:
        ledger = getattr(retaining_team, "retained_salary", None) or []
        active_ids = {e.get("player_id") for e in ledger
                      if int(e.get("seasons_remaining", 0) or 0) > 0}
        pid = getattr(player, "id", None)
        others = {str(k) for k in (extra or {}).keys()} - {str(pid)}
        others -= {str(_i) for _i in active_ids}
        if len(active_ids) + len(others) + (0 if pid in active_ids else 1) \
                > MAX_RETENTION_SLOTS:
            return False, 0, (
                f"{getattr(retaining_team, 'team_name', 'That club')} would "
                f"exceed the {MAX_RETENTION_SLOTS} retention-slot limit.")
    except Exception:
        pass
    effective = salary - int(getattr(player, "retained_amount", 0) or 0)
    amount = int(round(effective * pct / 100.0))
    if amount <= 0 or int(getattr(player, "retained_amount", 0) or 0) + amount >= salary:
        return False, 0, "Retention would wipe out the whole cap hit."
    # Real CBA: one contract can have salary retained by at most TWO clubs
    # (the classic double-retention: e.g. 50% then 50%-of-remainder).
    try:
        prior_teams = list(getattr(player, "retained_by", None) or [])
        _first = str(getattr(player, "retained_team_name", "") or "")
        if _first and _first not in prior_teams:
            prior_teams.append(_first)
        _me = str(getattr(retaining_team, "team_name", "") or "")
        if _me and _me not in prior_teams and len(prior_teams) >= 2:
            return False, 0, (
                "A contract can have salary retained by at most two clubs.")
    except Exception:
        pass
    # Real CBA: aggregate retained cap hits may not exceed 15% of the cap
    # upper limit in any league year (measured on full-season amounts).
    try:
        from salary_cap_system import retained_charge
        upper = int(getattr(retaining_team, "salary_cap", 0) or 0)
        if upper > 0:
            active_total = int(retained_charge(retaining_team))
            if active_total + amount > int(upper * 0.15):
                return False, 0, (
                    f"{getattr(retaining_team, 'team_name', 'That club')} would "
                    f"exceed the 15% retained-salary aggregate "
                    f"(${int(upper * 0.15):,} of a ${upper:,} cap).")
    except Exception:
        pass
    return True, amount, ""


def apply_retention_dry_run(retaining_team, player, pct, extra=None):
    """Validate retention terms without recording anything (for UI)."""
    ok, _amount, reason = _retention_check(retaining_team, player, pct, extra)
    return ok, (reason or "OK")


def apply_retention(retaining_team, player, pct) -> Tuple[bool, str]:
    """Record a retained-salary transaction when a player is traded.

    Real NHL rules: the trading club may keep up to 50% of the player's
    CURRENT effective cap hit; max 3 active retentions per club; the
    retained amount becomes dead cap on the retaining club for the
    remaining term of the contract, and the player's cap hit drops for
    his new club. Additive -- existing trades without retention are
    untouched. Returns (True, note) or (False, reason).
    """
    ok, amount, reason = _retention_check(retaining_team, player, pct)
    if not ok:
        return False, reason
    contract = getattr(player, "contract", None)
    years = int(getattr(contract, "years_remaining", 0) or 0) if contract else 0
    try:
        pct = float(pct or 0)
        ledger = getattr(retaining_team, "retained_salary", None)
        if ledger is None:
            ledger = []
            retaining_team.retained_salary = ledger
        ledger.append({
            "player_id": getattr(player, "id", None),
            "player_name": getattr(player, "full_name", str(player)),
            "amount": amount,
            "seasons_remaining": max(1, years),
        })
        player.retained_amount = int(getattr(player, "retained_amount", 0) or 0) + amount
        _rname = getattr(retaining_team, "team_name", "")
        if not getattr(player, "retained_team_name", ""):
            player.retained_team_name = _rname
        # Distinct retaining clubs on this contract (real CBA: max two).
        try:
            _by = list(getattr(player, "retained_by", None) or [])
            if _rname and _rname not in _by:
                _by.append(_rname)
            player.retained_by = _by
        except Exception:
            pass
    except Exception as e:
        return False, f"Could not record retention: {e}"
    return True, (f"{getattr(retaining_team, 'team_name', 'Club')} retains "
                  f"${amount:,} ({pct:g}%) of "
                  f"{getattr(player, 'full_name', 'the player')}'s cap hit.")


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
        desc = asset.description
        prot = protection_label(getattr(asset, "protection", ""))
        return f"{desc} ({prot})" if prot else desc
    try:
        label = f"{asset.full_name} ({asset.primary_position.value}, {asset.overall_rating()} OVR)"
    except Exception:
        return str(asset)
    try:
        ret = int(getattr(asset, "retained_amount", 0) or 0)
        if ret > 0:
            label += f" [${ret / 1e6:.2f}M retained]"
    except Exception:
        pass
    return label


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


def _player_cap_hit(p) -> int:
    """Cap hit of a trade asset: the salary on its contract.

    Player carries no bare ``.salary`` attribute -- it lives on
    ``p.contract.salary``. The old code read ``getattr(p, 'salary', 0)``,
    which was always 0, so outgoing/incoming money never registered:
    an over-cap club failed the check on every deal, even pure
    salary dumps. This restores cap-shedding trades for both sides.

    Retained salary (p.retained_amount, kept as dead cap by a former
    club) lowers the hit for the player's current club.
    """
    try:
        contract = getattr(p, "contract", None)
        if contract is not None:
            hit = int(getattr(contract, "salary", 0) or 0)
            hit -= int(getattr(p, "retained_amount", 0) or 0)
            return max(0, hit)
    except Exception:
        pass
    try:
        return int(getattr(p, "salary", 0) or 0)
    except Exception:
        return 0


def _retention_adjustment(assets, retention) -> int:
    """New dead-cap dollars a side keeps by retaining on outgoing assets.

    ``retention`` maps player id -> pct (1-50). Pure helper so the cap
    check and the UI meter agree.
    """
    total = 0
    if not retention:
        return 0
    for p in assets or []:
        if _is_pick(p):
            continue
        try:
            pct = float(retention.get(getattr(p, "id", None), 0) or 0)
        except Exception:
            pct = 0
        if pct > 0:
            total += int(round(_player_cap_hit(p) * min(pct, MAX_RETENTION_PCT) / 100.0))
    return total


def _cap_ok_after(team, outgoing, incoming, retention=None) -> bool:
    """Cap legality of a trade -- identical rule for AI and user.

    Dead-cap penalties count in the pre/post totals but never move as part
    of a player trade.

    - Club currently cap-compliant: the resulting total cap charge must
      stay at or under the cap.
    - Club currently OVER the cap: the trade is legal iff it STRICTLY
      reduces the total cap burden (a genuine salary shed), even if the
      club remains over afterward. Neutral or worsening deals are
      rejected -- you can't tread water or dig deeper while over.

    ``retention`` (optional, player id -> pct) models proposed
    retained-salary terms: the retaining side keeps that slice as dead
    cap, the receiving side's incoming hit drops by the same slice.
    """
    try:
        from salary_cap_system import total_cap_charge
        cap = int(team.salary_cap)
        current = int(total_cap_charge(team))
    except Exception:
        return True
    out_sal = sum(_player_cap_hit(p) for p in outgoing
                  if not _is_pick(p))
    in_sal = sum(_player_cap_hit(p) for p in incoming
                 if not _is_pick(p))
    # Retention: the retaining side's outgoing money partly stays home as
    # dead cap; the receiving side's incoming money drops by the same.
    kept_home = _retention_adjustment(outgoing, retention)
    relief_in = _retention_adjustment(incoming, retention)
    resulting = current - out_sal + kept_home + in_sal - relief_in
    if current <= cap:
        return resulting <= cap
    # Over the cap: only a strict reduction of the burden is legal.
    return resulting < current


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
                      user_team=None, patience=1.0, situational=None,
                      retention=None) -> AIResponse:
    """AI GM evaluates your offer. Returns accept / reject / counter.

    patience: 1.0 = fresh talks. Drops each counter round; a tired GM
    drives a harder bargain (higher effective greed) and is likelier
    to walk away than counter.

    situational: optional dict from trade_storylines.situational_context()
    with a 'greed_mult' nudge (<1 = more eager, >1 = harder bargain).
    Purely additive -- None means classic behavior.

    retention: optional player id -> pct map of proposed retained-salary
    terms; the AI's cap check sees the reduced incoming hit, exactly
    like a real GM pricing retained money.
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

    # Cap reality check (retention-aware: retained money costs the AI less)
    if not _cap_ok_after(partner_team, partner_assets, user_assets,
                         retention=retention):
        return AIResponse('reject',
                          f"We can't make the money work under the cap.")

    # Trade protection: the AI GM knows his own room. A clause player the
    # user demands must agree to waive for the user's team -- if he won't,
    # the deal is dead, and the AI says so plainly.
    if user_team is not None:
        for _v in trade_vetoes(partner_team, user_team, partner_assets):
            _p = _v["player"]
            _pname = getattr(_p, "full_name", str(_p))
            _ok, _why = will_waive_ntc(_p, partner_team, user_team)
            if not _ok:
                return AIResponse('reject', _why)
            try:
                _p.contract.ntc_waiver_for = getattr(user_team, 'team_name', '')
            except Exception:
                pass

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
                # The AI GM knows his own room: a player whose clause vetoes
                # a move to your team is only offered if he'd waive -- and
                # the granted waiver is stamped so completion honors it.
                if trade_vetoes(partner_team, user_team, [s]):
                    ok, _why = will_waive_ntc(s, partner_team, user_team)
                    if not ok:
                        continue
                    try:
                        s.contract.ntc_waiver_for = getattr(
                            user_team, 'team_name', '')
                    except Exception:
                        pass
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


# ============================================================================
# CONTRACT CLAUSE NEGOTIATION -- shared by user talks, AI signings, and both
# contract UIs. One valuation so nobody gets a private mechanic.
# ============================================================================

CLAUSE_KINDS = ("none", "nmc", "ntc", "mntc")

# Fraction of the player's market rate a clause is "worth" to him per year.
_CLAUSE_FRAC = {"nmc": 0.07, "ntc": 0.05, "mntc": 0.03, "none": 0.0}


def clause_eligible(player) -> bool:
    """Real NHL: only UFA-eligible players may hold trade protection.

    A player must be at least 27 years old at the start of the league year
    or have 7+ accrued pro seasons (the same bar as unrestricted free
    agency). Protection can kick in for the UFA years of a longer deal --
    the game models that as eligibility at signing time for simplicity.
    """
    try:
        age = int(getattr(player, "age", 0) or 0)
    except Exception:
        age = 0
    try:
        svc = int(getattr(player, "seasons_played", 0) or 0)
    except Exception:
        svc = 0
    return age >= 27 or svc >= 7


def clause_demand_score(player, team=None, league=None):
    """0..1 -- how hard this player pushes for trade protection in talks.

    Driven by leverage (established stars), age (veterans want stability),
    and loyalty (low-loyalty players want contractual control). Kids and
    journeymen don't get to ask -- and anyone below UFA eligibility
    (27+ / 7 seasons) can't hold a clause at all, so demand is zero.
    """
    try:
        if not clause_eligible(player):
            return 0.0
    except Exception:
        pass
    score = 0.0
    try:
        ovr = player.overall_rating()
    except Exception:
        ovr = 70
    age = getattr(player, "age", 27)
    if ovr >= 85:
        score += 0.45
    elif ovr >= 80:
        score += 0.25
    elif ovr >= 75:
        score += 0.10
    if age >= 32:
        score += 0.25
    elif age >= 29:
        score += 0.15
    try:
        from reputation_system import contract_loyalty
        if contract_loyalty(player) < 0.35:
            score += 0.15
    except Exception:
        pass
    # Cup-chasing veterans on contenders would rather keep their options
    # open than lock in -- slight cooling.
    try:
        if team is not None and league is not None \
                and _team_points_pct(team, league) >= 0.60 and age >= 33:
            score -= 0.10
    except Exception:
        pass
    return max(0.0, min(1.0, score))


def clause_annual_value(player, kind):
    """Dollar value the player attaches to a clause, per year.

    A star's NMC is worth real money to him (~7% of his market rate);
    a depth player's clause barely moves the needle.
    """
    if kind in (None, "none"):
        return 0
    try:
        base = max(750_000, (player.overall_rating() - 60) * 250_000)
    except Exception:
        base = 1_000_000
    frac = _CLAUSE_FRAC.get(kind, 0.0)
    return int(base * frac)


def clause_acceptance_bonus(player, kind):
    """0..0.2 bump to a probabilistic acceptance roll, scaled by demand."""
    if kind in (None, "none"):
        return 0.0
    return 0.20 * clause_demand_score(player)


def clause_offer_label(kind, list_size=10):
    if kind == "nmc":
        return "no-movement clause"
    if kind == "ntc":
        return "full no-trade clause"
    if kind == "mntc":
        return f"modified no-trade ({list_size}-team list)"
    return "no trade protection"


def apply_clause_to_contract(contract, kind, list_size=10, player=None):
    """Stamp a negotiated clause onto a fresh contract. Returns True.

    player (optional): when given, the real UFA-eligibility bar applies --
    a 23-year-old can't walk away with a no-movement clause.
    """
    if contract is None or kind in (None, "none"):
        return False
    try:
        if player is not None and not clause_eligible(player):
            return False
    except Exception:
        pass
    try:
        if kind == "nmc":
            contract.no_movement_clause = True
        else:
            contract.no_trade_clause = True
            if kind == "mntc":
                contract.modified_ntc_teams = int(list_size or 10)
        return True
    except Exception:
        return False


def execute_trade(user_team, partner_team, user_assets, partner_assets,
                  date_str="", league=None, board=None, retention=None) -> CompletedTrade:
    """Move players and picks. Assumes the deal was accepted.

    league/board are optional: when provided (user-involved deals), the
    trade's fallout is scored -- GM stature moves, the fleeced GM holds a
    personal grudge, and the board logs it via record_big_event. The asset
    movement itself is untouched.

    retention (optional, player id -> pct): retained-salary terms.
    Preflighted BEFORE the move (an illegal term blocks the whole deal);
    applied after, with the retaining club being whichever side traded the
    player away. Real NHL limits (50% per deal, 3 slots, 15% aggregate,
    max two retaining clubs, one-year reacquire ban) are enforced.

    No-trade/no-movement preflight: a clause veto in either direction that
    was never waived (contract.ntc_waiver_for) kills the deal BEFORE any
    asset moves -- the returned CompletedTrade carries the veto in its
    summary and moves nothing.

    League-office validation: the completed deal must also leave both
    clubs cap-legal (with the over-cap shedding exception), and every
    asset must actually be owned by the side trading it. Anything illegal
    blocks the whole deal; no assets move.
    """
    from game_classes import DraftPick

    def _blocked(summary):
        return CompletedTrade(
            date=date_str, team_a=user_team.team_name,
            team_b=partner_team.team_name, a_gave=[], b_gave=[],
            summary=f"BLOCKED: {summary} No assets moved.")

    # -- Asset ownership: you can't trade what you don't own.
    for _src_team, _assets in ((user_team, user_assets),
                               (partner_team, partner_assets)):
        _sname = getattr(_src_team, "team_name", "?")
        _roster = getattr(_src_team, "roster", None)
        for a in _assets or []:
            if isinstance(a, DraftPick):
                if str(getattr(a, "current_team", "") or "") != str(_sname):
                    return _blocked(
                        f"{_sname} doesn't own the "
                        f"{getattr(a, 'year', '?')} {getattr(a, 'round', '?')}"
                        f" round pick it offered.")
            elif _roster is not None and a not in _roster:
                _pname = getattr(a, "full_name", str(a))
                return _blocked(
                    f"{_pname} isn't on {_sname}'s roster.")

    # Retention preflight -- every term validated BEFORE anything moves.
    # An illegal term (over 50%, no slot left, 15% aggregate breached,
    # third retaining club, no cap hit to retain) kills the deal instead
    # of silently changing its economics mid-trade.
    #
    # Terms are split PER SIDE first: only the retaining club's own terms
    # consume its slots (the old code counted the other side's terms too).
    _team_terms = {}  # id(team) -> {player_id_str: pct} for ITS outgoing
    _all_terms = {}
    if retention:
        for _k, _v in retention.items():
            try:
                if float(_v or 0) > 0:
                    _all_terms[str(_k)] = float(_v)
            except Exception:
                pass
    for _src_team, _assets in ((user_team, user_assets),
                               (partner_team, partner_assets)):
        _mine = {}
        for a in _assets or []:
            if isinstance(a, DraftPick):
                continue
            _pct = _all_terms.get(str(getattr(a, "id", None)), 0)
            if _pct > 0:
                _mine[str(getattr(a, "id", None))] = _pct
        _team_terms[id(_src_team)] = _mine
    if retention:
        for _src_team, _assets in ((user_team, user_assets),
                                   (partner_team, partner_assets)):
            _mine = _team_terms.get(id(_src_team), {})
            _new_amounts = []
            for a in _assets:
                if isinstance(a, DraftPick):
                    continue
                _pct = _mine.get(str(getattr(a, "id", None)), 0)
                if _pct > 0:
                    _extra = {k: v for k, v in _mine.items()
                              if k != str(getattr(a, "id", None))}
                    ok, _amt, reason = _retention_check(
                        _src_team, a, _pct, extra=_extra)
                    if not ok:
                        _pname = getattr(a, "full_name", str(a))
                        return _blocked(
                            f"retained-salary term on {_pname} is illegal "
                            f"({reason}).")
                    _new_amounts.append(_amt)
            # Joint 15% aggregate: several new terms in one deal can breach
            # it together even when each passes alone.
            if _new_amounts:
                try:
                    from salary_cap_system import retained_charge
                    _upper = int(getattr(_src_team, "salary_cap", 0) or 0)
                    if _upper > 0:
                        _total = int(retained_charge(_src_team)) + sum(_new_amounts)
                        if _total > int(_upper * 0.15):
                            return _blocked(
                                f"{getattr(_src_team, 'team_name', 'That club')} "
                                f"would exceed the 15% retained-salary "
                                f"aggregate with this deal's terms.")
                except Exception:
                    pass
    # One-year reacquire ban: a club that retained salary on a player may
    # not reacquire him for a year (real CBA; the ban lifts if his deal
    # expired and he re-signed -- a new contract clears retention state).
    # Checked on EVERY deal, not just ones with new retention terms.
    for _acq_team, _assets in ((user_team, partner_assets),
                               (partner_team, user_assets)):
            _aname = str(getattr(_acq_team, "team_name", "") or "")
            for a in _assets or []:
                if isinstance(a, DraftPick):
                    continue
                for _ban in (getattr(a, "retention_bans", None) or []):
                    try:
                        if str(_ban.get("team", "")) != _aname:
                            continue
                        from datetime import date as _date
                        _ban_d = _date.fromisoformat(str(_ban.get("date", ""))[:10])
                        _now_d = _date.fromisoformat(str(date_str)[:10])
                        if 0 <= (_now_d - _ban_d).days < 365:
                            _pname = getattr(a, "full_name", str(a))
                            return _blocked(
                                f"{_aname} retained salary on {_pname} less "
                                f"than a year ago and can't reacquire him yet.")
                    except Exception:
                        continue
    # Clause preflight -- both directions, before anything moves.
    for _src, _dst, _assets in ((user_team, partner_team, user_assets),
                               (partner_team, user_team, partner_assets)):
        vetoes = trade_vetoes(_src, _dst, _assets, league)
        if vetoes:
            v = vetoes[0]
            pname = getattr(v["player"], "full_name", str(v["player"]))
            return _blocked(
                f"{pname} used his {v['detail']} to veto "
                f"the move to {_dst.team_name}.")
    # Cap legality -- the league office rejects cap-violating deals, for
    # AI and user clubs alike. Retention terms are modeled: the retaining
    # side keeps the slice as dead cap, the receiving side's hit drops.
    _ret_map = {}
    for _k, _v in _all_terms.items():
        _ret_map[_k] = _v  # string form
        try:
            _ret_map[int(_k)] = _v  # raw-id form (_retention_adjustment)
        except Exception:
            pass
    for _team, _out, _inc in ((user_team, user_assets, partner_assets),
                              (partner_team, partner_assets, user_assets)):
        if not _cap_ok_after(_team, _out, _inc, retention=_ret_map):
            return _blocked(
                f"the deal leaves {getattr(_team, 'team_name', 'a club')} "
                f"over the salary cap.")
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

    # Retained salary: record each term against the club that traded the
    # player away. Terms were preflighted above, so failures here are
    # unexpected -- still guarded, never fatal to the completed move.
    retention_notes = []
    if retention:
        for _src_team, _assets in ((user_team, user_assets),
                                   (partner_team, partner_assets)):
            for a in _assets:
                if isinstance(a, DraftPick):
                    continue
                try:
                    pct = float(retention.get(getattr(a, "id", None), 0) or 0)
                except Exception:
                    pct = 0
                if pct > 0:
                    ok, note = apply_retention(_src_team, a, pct)
                    if ok:
                        retention_notes.append(note)
                        # Real CBA: the retaining club may not reacquire
                        # this player for one year.
                        try:
                            _bans = list(getattr(a, "retention_bans", None) or [])
                            _bans.append({
                                "team": getattr(_src_team, "team_name", ""),
                                "date": str(date_str or "")[:10],
                            })
                            a.retention_bans = _bans[-8:]
                        except Exception:
                            pass
                    else:
                        print(f"retention skipped: {note}")

    a_labels = [asset_label(a) for a in user_assets]
    b_labels = [asset_label(a) for a in partner_assets]
    # Waivers are spent: a granted waiver covered this one transaction.
    for a in list(user_assets) + list(partner_assets):
        try:
            if not _is_pick(a) and getattr(a, "contract", None) is not None:
                a.contract.ntc_waiver_for = ""
        except Exception:
            pass
    summary = (f"{user_team.team_name} acquires {', '.join(b_labels)} from "
               f"{partner_team.team_name} for {', '.join(a_labels)}.")
    if retention_notes:
        summary += " " + " ".join(retention_notes)
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
    # AI press parity (module 03): the user's press answers ripple through
    # the user's room via media_system.handle_media_response. AI clubs get
    # the same cascade with an automatically chosen answer -- the user's own
    # team is excluded because the user answers for themselves. Fires once
    # per side per trade, after the per-player cascades above.
    try:
        import dressing_room as _dr
        moved_names = []
        for a in list(user_assets) + list(partner_assets):
            if isinstance(a, DraftPick):
                continue
            nm = getattr(a, "name", None) or getattr(a, "full_name", "")
            if nm:
                moved_names.append(str(nm))
        if moved_names:
            press_event = {"players_involved": moved_names, "trade": True}
            for side in (user_team, partner_team):
                # Human-run clubs (local or MP) do their own press; AI clubs
                # get the automated response.
                _hum = False
                try:
                    import game_classes as _gc
                    _hum = bool(_gc.is_human_managed(side))
                except Exception:
                    _hum = bool(getattr(side, "is_user_team", False))
                if _hum:
                    continue
                _dr.auto_press_response(side, press_event)
    except Exception:
        pass
