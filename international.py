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
from typing import Any, Dict, List, Optional, Tuple

OLYMPIC_MONTH, OLYMPIC_DAY = 2, 10
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


def _pname(p: Any) -> str:
    try:
        return p.full_name()
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


def _build_roster(pool: List[Tuple[Any, Any]],
                  nation: str) -> Dict[str, Any]:
    members = [(p, t) for p, t in pool if _nation_of(p) == nation]
    skaters = sorted([m for m in members if not _is_goalie(m[0])],
                     key=lambda m: _overall(m[0]), reverse=True)
    goalies = sorted([m for m in members if _is_goalie(m[0])],
                     key=lambda m: _overall(m[0]), reverse=True)
    roster = skaters[:SKATERS_PER_ROSTER] + goalies[:GOALIES_PER_ROSTER]
    # Strength is inclusive of every implemented player factor: effective
    # overall (form + morale), goalies weighted 1.6x (short tournaments
    # ride the hot goalie), plus the roster's chemistry bonus.
    sk_eff = [_effective_overall(p) for p, _ in roster
              if not _is_goalie(p)]
    gk_eff = [_effective_overall(p) for p, _ in roster if _is_goalie(p)]
    wsum = sum(sk_eff) + 1.6 * sum(gk_eff)
    w = len(sk_eff) + 1.6 * len(gk_eff)
    strength = (wsum / max(1.0, w)) + _bond_bonus(roster)
    return {"nation": nation, "roster": roster, "strength": strength}


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

def _hold(app: Any, year: int, event: str, title: str, worlds: bool,
          injury_pct: float, max_injury_games: int,
          rng: Optional[random.Random] = None) -> Optional[Dict[str, Any]]:
    rng = rng or random.Random()
    league = getattr(app, "league", None)
    if league is None:
        return None
    pool = _eligible_players(league, worlds)
    nations = _pick_nations(pool)
    if len(nations) < 2:
        return None
    rosters = {n: _build_roster(pool, n) for n in nations}
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
        **cons,
    }
    try:
        hist = getattr(league, "intl_history", None)
        if hist is None:
            league.intl_history = []
            hist = league.intl_history
        hist.append({k: result[k] for k in
                     ("event", "title", "year", "gold", "silver",
                      "bronze")})
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
