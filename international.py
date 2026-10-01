# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""International windows (additive, spectacle wave).

Two lightweight, instantly-resolved tournaments:

- Olympics: February 10 of Olympic years (year % 4 == 2), best-on-best.
  NHL roster players by nationality (injured players stay home).
- World Championship: May 12 every year. Players from non-playoff NHL
  teams plus prospects -- this is where crossovers happen.

Resolution is deliberately light: up to 8 nations, single-elim bracket,
team strength = effective overall (form + morale), goalies weighted 1.6x,
plus roster chemistry (NHL-club pairs + prior-tournament bonds), then noise. No games are simmed; the cost is
one pass over NHL rosters per tournament.

Consequences (the teeth):
- Bonds: NHL teammates who go together gain intl_bonds, read by
  line_chemistry_report (player_archetypes.py) as a small positive driver.
- Injury risk: ~6% Olympics / ~3% Worlds, minor injuries via the standard
  injury fields.
- Reputation: gold +8 / silver +5 / bronze +3 / tournament MVP +5
  (ratchet-safe: only ever added).
- Crossovers: the best U23 non-star gets a news note + reputation bump.
- Ledger memory: results recorded (weight 35).

Public API:
- hold_olympics(app, year) / hold_worlds(app, year) -> result dict.
- is_olympic_year(year)
- intl_bond(p1, p2) -> bond strength (0 if none).
"""

import random
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

OLYMPIC_MONTH, OLYMPIC_DAY = 2, 10          # legacy single-day hook (kept)
OLYMPIC_ANNOUNCE_MONTH, OLYMPIC_ANNOUNCE_DAY = 2, 9   # rosters + coaches
OLYMPIC_MEDAL_MONTH, OLYMPIC_MEDAL_DAY = 2, 22        # tournament resolved
OLYMPIC_BREAK_START_DAY, OLYMPIC_BREAK_END_DAY = 10, 24  # NHL goes dark
WORLDS_MONTH, WORLDS_DAY = 5, 12

CANDIDATE_NATIONS = [
    "Canada", "USA", "Sweden", "Finland", "Russia", "Czechia",
    "Switzerland", "Germany", "Slovakia", "Latvia",
]

SKATERS_PER_ROSTER = 18
GOALIES_PER_ROSTER = 2

GOLD_REP, SILVER_REP, BRONZE_REP, MVP_REP, CROSSOVER_REP = 8, 5, 3, 5, 5


def is_olympic_year(year: int) -> bool:
    return year % 4 == 2


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def _nation_of(player: Any) -> str:
    nat = (getattr(player, "nationality", "") or "").strip().lower()
    if not nat:
        return ""
    if "canad" in nat:
        return "Canada"
    if nat in ("usa", "u.s.a.", "united states", "american"):
        return "USA"
    if "russia" in nat:
        return "Russia"
    if "swed" in nat:
        return "Sweden"
    if "finl" in nat or "finn" in nat:
        return "Finland"
    if "czech" in nat:
        return "Czechia"
    if "switz" in nat or nat.startswith("swi"):
        return "Switzerland"
    if "german" in nat:
        return "Germany"
    if "slovak" in nat:
        return "Slovakia"
    if "latvia" in nat:
        return "Latvia"
    return ""


def _overall(p: Any) -> float:
    try:
        return float(p.overall_rating())
    except Exception:
        try:
            return float(getattr(p, "overall", 70))
        except Exception:
            return 70.0


def _is_goalie(p: Any) -> bool:
    try:
        return getattr(getattr(p, "primary_position", None), "name", "") == "GOALIE"
    except Exception:
        return False


def _is_dman(p: Any) -> bool:
    try:
        pos = getattr(getattr(p, "primary_position", None),
                      "value", "") or ""
        return str(pos).upper() in ("D", "LD", "RD")
    except Exception:
        return False


def _pname(p: Any) -> str:
    # full_name is a property on Player (game_classes.py); some callers pass
    # duck-typed objects where it may be a method. Handle both.
    # Fixed 2026-10-01 (playthrough BUG-REVIEW-001): p.full_name() raised
    # TypeError on the property, so every Olympic roster name rendered
    # "Unknown".
    try:
        _fn = p.full_name
        return _fn() if callable(_fn) else str(_fn)
    except Exception:
        return getattr(p, "name", "Unknown")


def _nhl_teams(league: Any) -> List[Any]:
    try:
        return [t for t in (getattr(league, "teams", []) or [])
                if getattr(t, "league_name", "") == "National Hockey League"]
    except Exception:
        return []


def _playoff_team_names(league: Any) -> set:
    try:
        br = getattr(league, "playoff_bracket", None)
        if br is None:
            return set()
        teams = list(getattr(br, "eastern_teams", []) or []) + \
            list(getattr(br, "western_teams", []) or [])
        return {getattr(t, "team_name", "") for t in teams}
    except Exception:
        return set()


def _eligible_players(league: Any, worlds: bool) -> List[Tuple[Any, Any]]:
    """(player, nhl_team) eligible for the tournament."""
    playoff = _playoff_team_names(league) if worlds else set()
    out = []
    for team in _nhl_teams(league):
        if worlds and getattr(team, "team_name", "") in playoff:
            continue
        pool = list(getattr(team, "roster", []) or [])
        if worlds:
            pool += list(getattr(team, "prospects", []) or [])
        for p in pool:
            if getattr(p, "is_injured", False):
                continue
            nation = _nation_of(p)
            if nation in CANDIDATE_NATIONS:
                out.append((p, team))
    return out


def _pick_nations(pool: List[Tuple[Any, Any]]) -> List[str]:
    by_nation: Dict[str, List] = {}
    for p, t in pool:
        by_nation.setdefault(_nation_of(p), []).append((p, t))
    # Nations that can ice a team: 14+ skaters and a goalie.
    viable = []
    for nation in CANDIDATE_NATIONS:
        members = by_nation.get(nation, [])
        skaters = [m for m in members if not _is_goalie(m[0])]
        goalies = [m for m in members if _is_goalie(m[0])]
        if len(skaters) >= 14 and goalies:
            viable.append(nation)
    return viable[:8]


# ---------------------------------------------------------------------------
# Olympic coaches
#
# Each federation appoints a head coach of its own nationality. The
# pecking order mirrors real appointments (Cooper for Canada, Sullivan
# for the USA): reputation first, then recency -- Cups won lately and
# how hot his NHL club is right now. Nationality is a hard filter.
# ---------------------------------------------------------------------------

def _is_head_coach(s: Any) -> bool:
    try:
        return str(getattr(getattr(s, "role", None), "name", "")) \
            == "HEAD_COACH"
    except Exception:
        return False


def _nhl_head_coaches(league: Any) -> List[Tuple[Any, Any]]:
    out = []
    for t in _nhl_teams(league):
        for s in getattr(t, "staff", []) or []:
            if _is_head_coach(s):
                out.append((s, t))
    return out


def _recent_cups(coach: Any, year: int, window: int = 4) -> int:
    """Stanley Cups banked on the coach's card inside the window."""
    n = 0
    for a in getattr(coach, "career_accolades", []) or []:
        if not isinstance(a, dict) or a.get("award") != "stanley_cup":
            continue
        try:
            y0 = int(str(a.get("year", ""))[:4])
        except Exception:
            continue
        if year - window <= y0 <= year:
            n += 1
    return n


def _adams_count(coach: Any) -> int:
    return sum(1 for a in getattr(coach, "career_accolades", []) or []
               if isinstance(a, dict) and a.get("award") == "jack_adams")


def _points_pct(league: Any, team: Any) -> float:
    row = (getattr(league, "standings", {}) or {}).get(
        getattr(team, "team_name", ""), {}) or {}
    try:
        pts = float(row.get("Points", 0) or 0)
        gp = float(row.get("W", 0) or 0) + float(row.get("L", 0) or 0) \
            + float(row.get("OTL", 0) or 0)
    except Exception:
        return 0.5
    return (pts / (2.0 * gp)) if gp > 0 else 0.5


def _coach_score(league: Any, coach: Any, team: Any, year: int) -> float:
    """Appointment score: reputation + recency. Judgment-call weights:
    a recent Cup (+15) is worth ~15 reputation points; a .650 club right
    now is worth +26; a Jack Adams (+5) is durable peer respect."""
    rep = float(getattr(coach, "reputation", 50) or 50)
    return (rep + 15.0 * _recent_cups(coach, year)
            + 40.0 * _points_pct(league, team)
            + 5.0 * _adams_count(coach))


def select_olympic_coach(league: Any, nation: str, year: int,
                         rng: Optional[random.Random] = None
                         ) -> Tuple[Optional[Any], Optional[Any]]:
    """Pick the nation's Olympic head coach. Returns (coach, nhl_team).

    Hard rule: the coach's nationality must match the nation. Preferred:
    an NHL head coach, ranked by reputation + recency. Fallback: any
    coaching-staff member of that nationality; then (None, None).
    """
    cands = [(s, t) for s, t in _nhl_head_coaches(league)
             if _nation_of(s) == nation]
    if not cands:
        for t in _nhl_teams(league):
            for s in getattr(t, "staff", []) or []:
                try:
                    rn = str(getattr(getattr(s, "role", None),
                                     "name", ""))
                except Exception:
                    rn = ""
                if "COACH" in rn and _nation_of(s) == nation:
                    cands.append((s, t))
    if not cands:
        return None, None
    return max(cands, key=lambda st: _coach_score(league, st[0], st[1],
                                                  year))


def _coach_name(c: Any) -> str:
    try:
        return c.full_name
    except Exception:
        return str(getattr(c, "name", "Unknown"))


def _coach_profile(coach: Any) -> Dict[str, float]:
    """The coach's selection tendencies, 0..1, read off his attributes.

    - loyalty: man-managers bring their guys (same-club bump).
    - vet_lean: motivators trust veterans in short tournaments.
    - def_lean: tacticians pick two-way players over pure offense.
    """
    def _a(name: str) -> float:
        try:
            return max(1.0, min(99.0,
                                float(getattr(coach, name, 50) or 50)))
        except Exception:
            return 50.0

    def _n(v: float) -> float:
        return max(0.0, min(1.0, (v - 50.0) / 50.0))

    return {
        "loyalty": _n(_a("man_management")),
        "vet_lean": _n(_a("motivating")),
        "def_lean": _n((_a("tactical_knowledge") + _a("discipline")) / 2.0),
    }


def _coach_pick_score(p: Any, t: Any, base: float,
                      coach: Any, coach_team: Any,
                      profile: Dict[str, float],
                      gold_names: frozenset) -> float:
    """The coach's own hand on the roster: the base merit score plus his
    biases. His guys (+1..3), veterans he trusts (+0..2, kids -0..1), men
    who've won gold for the nation before (+2), and two-way players if
    he's a defense-first coach (+0..2)."""
    adj = base
    try:
        if (t is not None and coach_team is not None and t is coach_team):
            adj += 1.0 + 2.0 * profile["loyalty"]
    except Exception:
        pass
    try:
        age = int(getattr(p, "age", 27) or 27)
    except Exception:
        age = 27
    if age >= 32:
        adj += 2.0 * profile["vet_lean"]
    elif age <= 23:
        adj -= 1.0 * profile["vet_lean"]
    try:
        if _pname(p) in gold_names:
            adj += 2.0
    except Exception:
        pass
    if profile["def_lean"] > 0 and not _is_goalie(p):
        try:
            da = float(getattr(p, "defensive_awareness", 50) or 50)
        except Exception:
            da = 50.0
        if da >= 70:
            adj += 2.0 * profile["def_lean"]
    return adj


def _effective_overall(p: Any) -> float:
    """Overall adjusted by everything the game already tracks.

    Form (mesh_form, -1 cold .. 1 hot) moves a player ~5% either way;
    morale (1-100) moves him 0.95x..1.05x. Short tournaments are won by
    hot players, not just talented ones.
    """
    base = _overall(p)
    try:
        form = max(-1.0, min(1.0, float(getattr(p, "mesh_form", 0.0) or 0.0)))
    except Exception:
        form = 0.0
    try:
        morale = max(1.0, min(100.0,
                              float(getattr(p, "morale", 70) or 70)))
    except Exception:
        morale = 70.0
    return base * (1.0 + 0.05 * form) * (0.95 + (morale / 100.0) * 0.10)


def _bond_bonus(roster: List[Tuple[Any, Any]]) -> float:
    """Chemistry bonus for a national roster (capped at +2.0).

    Countrymen who play together in the NHL arrive with chemistry
    (+0.15/pair); pairs forged at prior tournaments bring their
    intl_bonds (+0.25 per bond point). Familiarity wins short
    tournaments.
    """
    bonus = 0.0
    club_bonus = 0.0
    bond_pts = 0.0
    n = len(roster)
    for i in range(n):
        pi, ti = roster[i]
        for j in range(i + 1, n):
            pj, tj = roster[j]
            try:
                if ti is not None and tj is not None and ti is tj:
                    club_bonus += 0.15
            except Exception:
                pass
            try:
                bond_pts += _bond_entry(pi, pj)[0]
            except Exception:
                pass
    bonus = min(1.0, club_bonus) + min(1.0, bond_pts * 0.25)
    return min(2.0, bonus)


FORWARDS_PER_ROSTER = 12
DMEN_PER_ROSTER = 6


def _roster_strength(roster: List[Tuple[Any, Any]]) -> float:
    """Strength is inclusive of every implemented player factor: effective
    overall (form + morale), goalies weighted 1.6x (short tournaments
    ride the hot goalie), plus the roster's chemistry bonus."""
    sk_eff = [_effective_overall(p) for p, _ in roster
              if not _is_goalie(p)]
    gk_eff = [_effective_overall(p) for p, _ in roster if _is_goalie(p)]
    wsum = sum(sk_eff) + 1.6 * sum(gk_eff)
    w = len(sk_eff) + 1.6 * len(gk_eff)
    return (wsum / max(1.0, w)) + _bond_bonus(roster)


def _build_roster(pool: List[Tuple[Any, Any]],
                  nation: str,
                  coach: Optional[Any] = None,
                  coach_team: Optional[Any] = None,
                  rng: Optional[random.Random] = None,
                  gold_names: frozenset = frozenset()
                  ) -> Dict[str, Any]:
    members = [(p, t) for p, t in pool if _nation_of(p) == nation]
    profile = _coach_profile(coach) if coach is not None else None
    scored = []
    for p, t in members:
        base = _effective_overall(p)
        s = (_coach_pick_score(p, t, base, coach, coach_team, profile,
                               gold_names)
             if profile is not None else base)
        scored.append((s, p, t))
    fw = sorted([x for x in scored
                 if not _is_goalie(x[1]) and not _is_dman(x[1])],
                key=lambda x: x[0], reverse=True)
    dm = sorted([x for x in scored
                 if _is_dman(x[1]) and not _is_goalie(x[1])],
                key=lambda x: x[0], reverse=True)
    gk = sorted([x for x in scored if _is_goalie(x[1])],
                key=lambda x: x[0], reverse=True)
    # Realistic shape: 12 forwards, 6 defensemen, 2 goalies. If the
    # nation is thin on the blue line, fill with the best skaters left.
    roster = ([(p, t) for _, p, t in fw[:FORWARDS_PER_ROSTER]]
              + [(p, t) for _, p, t in dm[:DMEN_PER_ROSTER]]
              + [(p, t) for _, p, t in gk[:GOALIES_PER_ROSTER]])
    if len([x for x in roster if not _is_goalie(x[0])]) < SKATERS_PER_ROSTER:
        have = {(id(p)) for p, _ in roster}
        rest = sorted([x for x in scored if id(x[1]) not in have
                       and not _is_goalie(x[1])],
                      key=lambda x: x[0], reverse=True)
        need = SKATERS_PER_ROSTER - \
            len([x for x in roster if not _is_goalie(x[0])])
        roster += [(p, t) for _, p, t in rest[:need]]
    return {"nation": nation, "roster": roster,
            "strength": _roster_strength(roster),
            "coach": coach, "coach_team": coach_team}


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _win_prob(a: float, b: float) -> float:
    # Logistic on strength gap; ~62% for a 2-point overall gap.
    import math
    return 1.0 / (1.0 + math.exp(-(a - b) * 0.25))


def _play_game(a: Dict[str, Any], b: Dict[str, Any],
               rng: random.Random) -> Dict[str, Any]:
    return a if rng.random() < _win_prob(a["strength"], b["strength"]) \
        else b


def _resolve_bracket(rosters: Dict[str, Dict[str, Any]],
                     rng: random.Random) -> Dict[str, Any]:
    seeds = sorted(rosters.values(), key=lambda r: r["strength"],
                   reverse=True)
    # QF: 1v8, 4v5, 3v6, 2v7.
    qf_pairs = [(0, 7), (3, 4), (2, 5), (1, 6)]
    qf_winners, qf_losers = [], []
    games = []
    for i, j in qf_pairs:
        if j >= len(seeds):
            qf_winners.append(seeds[i])
            continue
        w = _play_game(seeds[i], seeds[j], rng)
        games.append((seeds[i]["nation"], seeds[j]["nation"],
                      w["nation"]))
        qf_winners.append(w)
        qf_losers.append(seeds[j] if w is seeds[i] else seeds[i])
    sf_winners, sf_losers = [], []
    for k in (0, 1):
        if 2 * k + 1 >= len(qf_winners):
            sf_winners.append(qf_winners[2 * k])
            continue
        w = _play_game(qf_winners[2 * k], qf_winners[2 * k + 1], rng)
        games.append((qf_winners[2 * k]["nation"],
                      qf_winners[2 * k + 1]["nation"], w["nation"]))
        sf_winners.append(w)
        sf_losers.append(qf_winners[2 * k + 1]
                         if w is qf_winners[2 * k]
                         else qf_winners[2 * k])
    bronze_w = _play_game(sf_losers[0], sf_losers[1], rng) \
        if len(sf_losers) == 2 else None
    gold_w = _play_game(sf_winners[0], sf_winners[1], rng) \
        if len(sf_winners) == 2 else sf_winners[0]
    gold_l = sf_winners[1] if (len(sf_winners) == 2 and
                               gold_w is sf_winners[0]) \
        else (sf_winners[0] if len(sf_winners) == 2 else None)
    if bronze_w is not None:
        games.append((sf_losers[0]["nation"], sf_losers[1]["nation"],
                      bronze_w["nation"]))
    if len(sf_winners) == 2:
        games.append((sf_winners[0]["nation"], sf_winners[1]["nation"],
                      gold_w["nation"]))
    return {
        "gold": gold_w["nation"] if gold_w else "",
        "silver": gold_l["nation"] if gold_l else "",
        "bronze": bronze_w["nation"] if bronze_w else "",
        "games": games,
    }


def _tournament_scores(rosters: Dict[str, Dict[str, Any]],
                       rng: random.Random) -> List[Tuple[Any, Any, float]]:
    """Rolled per-player tournament production (for MVP / crossovers)."""
    out = []
    for r in rosters.values():
        champ_boost = 1.25 if r.get("_medal") == "gold" else 1.0
        for p, team in r["roster"]:
            base = _overall(p) / 18.0
            pts = max(0.0, rng.gauss(base * 4 * champ_boost, base))
            out.append((p, team, pts))
    out.sort(key=lambda x: x[2], reverse=True)
    return out


# ---------------------------------------------------------------------------
# Consequences
# ---------------------------------------------------------------------------

def _bump_rep(p: Any, amount: int) -> None:
    try:
        from reputation_system import ensure_reputation_fields
        ensure_reputation_fields(p)
        p.reputation = (getattr(p, "reputation", 0) or 0) + amount
    except Exception:
        pass


def _hurt(p: Any, rng: random.Random, max_games: int) -> str:
    p.is_injured = True
    p.injury_type = rng.choice(
        ["Bruised ribs", "Minor sprain", "Sore shoulder", "Tweaked knee",
         "Sprained ankle"])
    p.games_remaining_injured = rng.randint(1, max_games)
    p.last_injury = p.injury_type
    try:
        p.injured_today = True
    except Exception:
        pass
    return f"{_pname(p)} ({p.injury_type}, ~{p.games_remaining_injured} games)"


def intl_bond(p1: Any, p2: Any) -> int:
    """Bond strength between two players (0 if none)."""
    return _bond_entry(p1, p2)[0]


def intl_bond_event(p1: Any, p2: Any) -> str:
    """Which tournament forged the bond ('' if none)."""
    return _bond_entry(p1, p2)[1]


def _bond_entry(p1: Any, p2: Any) -> Tuple[int, str]:
    try:
        b1 = getattr(p1, "intl_bonds", None) or {}
        v = b1.get(_pname(p2))
        if isinstance(v, dict):
            return int(v.get("s", 0)), str(v.get("e", ""))
        return int(v or 0), ""
    except Exception:
        return 0, ""


def _add_bond(p1: Any, p2: Any, event: str, amount: int = 2,
              cap: int = 6) -> None:
    for a, b in ((p1, p2), (p2, p1)):
        try:
            bonds = getattr(a, "intl_bonds", None)
            if bonds is None:
                a.intl_bonds = {}
                bonds = a.intl_bonds
            n = _pname(b)
            cur = bonds.get(n)
            cur_s = cur.get("s", 0) if isinstance(cur, dict) else int(cur or 0)
            bonds[n] = {"s": min(cap, cur_s + amount), "e": event}
        except Exception:
            pass


def _apply_consequences(rosters: Dict[str, Dict[str, Any]],
                        bracket: Dict[str, Any],
                        scores: List[Tuple[Any, Any, float]],
                        event: str, rng: random.Random,
                        injury_pct: float, max_injury_games: int,
                        user_team_name: str = "") -> Dict[str, Any]:
    medal_rep = {"gold": GOLD_REP, "silver": SILVER_REP,
                 "bronze": BRONZE_REP}
    for medal in ("gold", "silver", "bronze"):
        nation = bracket.get(medal)
        if nation and nation in rosters:
            rosters[nation]["_medal"] = medal
            for p, _t in rosters[nation]["roster"]:
                _bump_rep(p, medal_rep[medal])

    # MVP: top scorer.
    mvp_line = ""
    if scores:
        mvp, mvp_team, mvp_pts = scores[0]
        _bump_rep(mvp, MVP_REP)
        mvp_line = (f"Tournament MVP: {_pname(mvp)} "
                    f"({getattr(mvp_team, 'team_name', '')}) -- "
                    f"{mvp_pts:.1f} pts")

    # Crossover: best U23 non-star.
    crossover_line = ""
    for p, team, pts in scores:
        try:
            age = getattr(p, "age", 99)
            rep = getattr(p, "reputation", 0) or 0
        except Exception:
            continue
        if age < 23 and rep < 40:
            _bump_rep(p, CROSSOVER_REP)
            crossover_line = (
                f"🌟 {_pname(p)} ({getattr(team, 'team_name', '')}, {age}) "
                f"announced himself on the world stage -- {pts:.1f} pts. "
                f"Remember the name.")
            break

    # Bonds: NHL teammates who went together.
    bonds_made = 0
    seen_teams: Dict[str, List[Any]] = {}
    for r in rosters.values():
        for p, team in r["roster"]:
            seen_teams.setdefault(getattr(team, "team_name", ""), []).append(p)
    for plist in seen_teams.values():
        for i in range(len(plist)):
            for j in range(i + 1, len(plist)):
                _add_bond(plist[i], plist[j], event)
                bonds_made += 1

    # Injuries.
    hurt_lines = []
    for r in rosters.values():
        for p, _t in r["roster"]:
            prone = getattr(p, "injury_proneness", 10) or 10
            if rng.random() < injury_pct * min(2.0, prone / 10.0):
                hurt_lines.append(_hurt(p, rng, max_injury_games))

    # User-team participants.
    user_lines = []
    for r in rosters.values():
        for p, team in r["roster"]:
            if getattr(team, "team_name", "") == user_team_name:
                user_lines.append(f"{_pname(p)} ({r['nation']})")

    return {
        "mvp_line": mvp_line,
        "crossover_line": crossover_line,
        "bonds_made": bonds_made,
        "hurt_lines": hurt_lines,
        "user_lines": sorted(set(user_lines)),
    }


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def _gold_medalist_names(league: Any) -> Dict[str, frozenset]:
    """Names of the last Olympic gold roster per nation (loyalty signal
    for the next coach's picks). Only entries recorded with rosters."""
    out: Dict[str, set] = {}  # type: ignore[valid-type]
    for h in getattr(league, "intl_history", None) or []:
        try:
            if h.get("event") != "olympics" or h.get("gold") is None:
                continue
            names = h.get("gold_roster") or []
            if names:
                out[h["gold"]] = set(names)
        except Exception:
            continue
    return {k: frozenset(v) for k, v in out.items()}


def _prepare(app: Any, year: int, event: str, worlds: bool,
             rng: random.Random):
    """Select nations, coaches (Olympics), and rosters. Returns
    (nations, rosters, coach_map) with live objects."""
    league = getattr(app, "league", None)
    if league is None:
        return [], {}, {}
    pool = _eligible_players(league, worlds)
    nations = _pick_nations(pool)
    if len(nations) < 2:
        return [], {}, {}
    gold_names = _gold_medalist_names(league) if not worlds else {}
    rosters: Dict[str, Dict[str, Any]] = {}
    coach_map: Dict[str, Tuple[Optional[Any], Optional[Any]]] = {}
    for n in nations:
        c, ct = (select_olympic_coach(league, n, year, rng)
                 if not worlds else (None, None))
        coach_map[n] = (c, ct)
        rosters[n] = _build_roster(
            pool, n, coach=c, coach_team=ct, rng=rng,
            gold_names=gold_names.get(n, frozenset()))
    return nations, rosters, coach_map


def _prep_to_plain(nations: List[str],
                   rosters: Dict[str, Dict[str, Any]],
                   coach_map: Dict[str, Tuple[Optional[Any], Optional[Any]]]
                   ) -> Dict[str, Any]:
    """Prep as plain data (save/load safe) for the announce→medal-day gap."""
    plain: Dict[str, Any] = {"nations": list(nations), "rosters": {}}
    for n in nations:
        r = rosters[n]
        c, ct = coach_map.get(n, (None, None))
        plain["rosters"][n] = {
            "player_ids": [getattr(p, "id", None) for p, _ in r["roster"]],
            "team_names": [getattr(t, "team_name", "") or ""
                           for _, t in r["roster"]],
            "coach_id": getattr(c, "id", None),
            "coach_name": _coach_name(c) if c is not None else None,
            "coach_team": getattr(ct, "team_name", "") or "",
        }
    return plain


def _rosters_from_prep(league: Any, prep: Dict[str, Any]
                       ) -> Dict[str, Dict[str, Any]]:
    """Rebuild live rosters from stored prep (medal day)."""
    by_id: Dict[Any, Tuple[Any, Any]] = {}
    for t in _nhl_teams(league):
        for p in getattr(t, "roster", []) or []:
            try:
                by_id[getattr(p, "id", None)] = (p, t)
            except Exception:
                pass
    rosters: Dict[str, Dict[str, Any]] = {}
    for n in prep.get("nations", []):
        rp = (prep.get("rosters", {}) or {}).get(n, {})
        pairs = [by_id[pid] for pid in (rp.get("player_ids") or [])
                 if pid in by_id]
        if not pairs:
            continue
        rosters[n] = {"nation": n, "roster": pairs,
                      "strength": _roster_strength(pairs)}
    return rosters


def _store_prep(league: Any, year: int, prep: Dict[str, Any]) -> None:
    try:
        slot = getattr(league, "intl_prep", None)
        if slot is None:
            league.intl_prep = slot = {}
        slot[year] = prep
    except Exception:
        pass


def _take_prep(league: Any, year: int) -> Optional[Dict[str, Any]]:
    try:
        return (getattr(league, "intl_prep", None) or {}).get(year)
    except Exception:
        return None


def olympic_announcement_text(year: int, nations: List[str],
                              rosters: Dict[str, Dict[str, Any]],
                              coach_map: Dict[str, Tuple[Optional[Any],
                                                         Optional[Any]]]
                              ) -> str:
    """Feb 9 news: the federations name coaches and rosters."""
    bits = []
    for n in nations:
        r = rosters.get(n, {})
        c, ct = coach_map.get(n, (None, None))
        coach_bit = (_coach_name(c) if c is not None else "TBD")
        if ct is not None:
            coach_bit += f" ({getattr(ct, 'team_name', '')})"
        skaters = sorted([p for p, _ in r.get("roster", [])
                          if not _is_goalie(p)],
                         key=_effective_overall, reverse=True)
        names = ", ".join(_pname(p) for p in skaters[:3])
        extra = max(0, len(skaters) - 3)
        bits.append(f"{n} -- HC {coach_bit}: {names}"
                    + (f" (+{extra} more)" if extra else ""))
    return (f"🏒 Olympic hockey {year}: the federations have named their "
            f"coaches and rosters -- " + " | ".join(bits)
            + ". The tournament runs February 10-22; the NHL goes dark "
            f"for the break.")


def announce_olympics(app: Any, year: int,
                      rng: Optional[random.Random] = None
                      ) -> Optional[str]:
    """Feb 9: pick nations, coaches, and rosters; store the prep for
    medal day. Returns the announcement story (None if no tournament)."""
    rng = rng or random.Random()
    nations, rosters, coach_map = _prepare(app, year, "olympics",
                                           worlds=False, rng=rng)
    if not nations:
        return None
    league = getattr(app, "league", None)
    _store_prep(league, year,
                _prep_to_plain(nations, rosters, coach_map))
    try:
        held = getattr(league, "intl_announced", None)
        if held is None:
            league.intl_announced = held = []
        if year not in held:
            held.append(year)
    except Exception:
        pass
    return olympic_announcement_text(year, nations, rosters, coach_map)


def _resolve(app: Any, year: int, event: str, title: str, worlds: bool,
             injury_pct: float, max_injury_games: int,
             rosters: Dict[str, Dict[str, Any]],
             coach_map: Dict[str, Tuple[Optional[Any], Optional[Any]]],
             rng: random.Random) -> Optional[Dict[str, Any]]:
    bracket = _resolve_bracket(rosters, rng)
    for medal in ("gold", "silver", "bronze"):
        if bracket.get(medal) in rosters:
            rosters[bracket[medal]]["_medal"] = medal
    scores = _tournament_scores(rosters, rng)
    user_team_name = getattr(getattr(app, "user_team", None),
                            "team_name", "") or ""
    cons = _apply_consequences(rosters, bracket, scores, f"{title} {year}",
                               rng, injury_pct, max_injury_games,
                               user_team_name)

    result = {
        "event": event, "title": title, "year": year,
        "gold": bracket["gold"], "silver": bracket["silver"],
        "bronze": bracket["bronze"], "games": bracket["games"],
        "coaches": {n: (_coach_name(c) if c is not None else None)
                    for n, (c, _t) in coach_map.items()},
        **cons,
    }
    try:
        league = getattr(app, "league", None)
        hist = getattr(league, "intl_history", None)
        if hist is None:
            league.intl_history = []
            hist = league.intl_history
        entry = {k: result[k] for k in
                 ("event", "title", "year", "gold", "silver",
                  "bronze")}
        try:
            if result["gold"] in rosters:
                entry["gold_roster"] = [
                    _pname(p) for p, _ in rosters[result["gold"]]["roster"]]
        except Exception:
            pass
        hist.append(entry)
        held = getattr(league, "intl_held", None)
        if held is None:
            league.intl_held = {"olympics": [], "worlds": []}
            held = league.intl_held
        if year not in held.get(event, []):
            held[event] = sorted(held.get(event, []) + [year])
    except Exception:
        pass
    try:
        from narrative_ledger import active_ledger
        led = active_ledger()
        if led is not None:
            _dup = any(e.get("kind") == "intl_tournament"
                       and e.get("facts", {}).get("event") == event
                       and e.get("facts", {}).get("year") == year
                       for e in led.events)
            if not _dup:
                led.record(
                    "intl_tournament", weight=35,
                    facts={"event": event, "year": year,
                           "gold": bracket["gold"],
                           "silver": bracket["silver"],
                           "bronze": bracket["bronze"]},
                    text=(f"{bracket['gold']} won {title} {year}, "
                          f"{bracket['silver']} silver, "
                          f"{bracket['bronze']} bronze."))
    except Exception:
        pass
    return result


def resolve_olympics(app: Any, year: int,
                     rng: Optional[random.Random] = None
                     ) -> Optional[Dict[str, Any]]:
    """Feb 22 (medal day): resolve the announced tournament."""
    rng = rng or random.Random()
    league = getattr(app, "league", None)
    if league is None:
        return None
    prep = _take_prep(league, year)
    if prep is None:
        # Announce and resolve back-to-back (old saves, QA).
        announce_olympics(app, year, rng)
        prep = _take_prep(league, year)
    if prep is None:
        return None
    rosters = _rosters_from_prep(league, prep)
    if len(rosters) < 2:
        return None
    coach_map = {}
    for n in prep.get("nations", []):
        rp = (prep.get("rosters", {}) or {}).get(n, {})
        # The announced coach's name rides along for the result card.
        coach_map[n] = (SimpleNamespace(
            full_name=rp.get("coach_name") or "TBD",
            name=rp.get("coach_name") or "TBD"), None)
    return _resolve(app, year, "olympics", "Olympic hockey", worlds=False,
                    injury_pct=0.06, max_injury_games=8,
                    rosters=rosters, coach_map=coach_map, rng=rng)


def _hold(app: Any, year: int, event: str, title: str, worlds: bool,
          injury_pct: float, max_injury_games: int,
          rng: Optional[random.Random] = None) -> Optional[Dict[str, Any]]:
    rng = rng or random.Random()
    if event == "olympics":
        # Announce then resolve (single-day path: QA, old callers).
        if announce_olympics(app, year, rng) is None:
            return None
        return resolve_olympics(app, year, rng)
    nations, rosters, coach_map = _prepare(app, year, event, worlds,
                                           rng)
    if not nations:
        return None
    return _resolve(app, year, event, title, worlds, injury_pct,
                    max_injury_games, rosters=rosters,
                    coach_map=coach_map, rng=rng)


def hold_olympics(app: Any, year: int,
                  rng: Optional[random.Random] = None) -> Optional[Dict[str, Any]]:
    """Best-on-best Olympic tournament (February, Olympic years)."""
    return _hold(app, year, "olympics", "Olympic hockey", worlds=False,
                 injury_pct=0.06, max_injury_games=8, rng=rng)


def hold_worlds(app: Any, year: int,
                rng: Optional[random.Random] = None) -> Optional[Dict[str, Any]]:
    """World Championship (May, non-playoff players + prospects)."""
    return _hold(app, year, "worlds", "World Championship", worlds=True,
                 injury_pct=0.03, max_injury_games=3, rng=rng)


def result_card_text(res: Dict[str, Any]) -> str:
    """Inbox-card body for a finished tournament."""
    if not res:
        return "The tournament could not be staged."
    L = [f"🥇 GOLD: {res['gold']}", f"🥈 SILVER: {res['silver']}",
         f"🥉 BRONZE: {res['bronze']}"]
    coaches = res.get("coaches") or {}
    named = [f"{n}: {c}" for n, c in coaches.items() if c]
    if named:
        L.extend(["", "Behind the benches:", *[f"  • {x}" for x in named]])
    if res.get("games"):
        L.append("")
        L.append("The road there:")
        for a, b, w in res["games"][-4:]:
            L.append(f"  {a} vs {b} -- {w} win")
    if res.get("mvp_line"):
        L.extend(["", res["mvp_line"]])
    if res.get("crossover_line"):
        L.extend(["", res["crossover_line"]])
    if res.get("user_lines"):
        L.extend(["", "Your players at the tournament:",
                  *[f"  • {u}" for u in res["user_lines"]]])
    if res.get("hurt_lines"):
        L.extend(["", "Injury room:",
                  *[f"  • {h}" for h in res["hurt_lines"]]])
    if res.get("bonds_made"):
        L.append(f"\n{res['bonds_made']} new international bonds forged "
                 f"between NHL teammates.")
    return "\n".join(L)
