"""Post-game narrative incidents + game stories (shared decision module).

One decision, two fidelities: GameSim models fights and brawls live while
the game is skated; AdvancedGameSim cannot -- so after the final horn we
roll the same dice here, using the same probability functions
(fight_probability, brawl_probability, game_tension from
reputation_system) and writing through the same record_game_incident()
path (league.rivalries + the narrative-ledger bridge). A brawl in a
quick-simmed game now heats the feud exactly like one you watched live.

Game stories (hat tricks, shutouts, goalie steals, statement blowouts, OT
thrillers) are recorded for BOTH engines: GameSim's story_worthy() only
ever drove the visualizer and never reached the ledger, so legendary
nights in watched games were forgotten too.

Everything written here goes through the established stores
(league.rivalries, NarrativeLedger); this module invents no persistence
of its own. Headline delivery stays the caller's job -- user-involved
games only, per the no-spam rule. Rates are conservative: the ledger
should remember the season's real stories, not every Tuesday.

Perf: one game_tension() scan (O(rivalries)) + a handful of RNG rolls per
game. Called once per finished game, never in a hot loop.
"""

import random
from typing import (Any, Dict, List, Optional)

# ---------------------------------------------------------------------------
# Tuning: realistic yet quiet. A full 82-game season per club, 1,312 games
# league-wide. Targets: ~0.26 fights/game (NHL average), line brawls ~0.2%
# of games, controversial hits under 1%, injuries left to the engines that
# model players getting hurt (GameSim / _process_gameplay_injuries).
# ---------------------------------------------------------------------------

_HAT_TRICK_WEIGHT = 15
_SHUTOUT_WEIGHT = 12
_STEAL_WEIGHT = 15        # 35+ saves in a win
_BLOWOUT_WEIGHT = 10      # 5+ goal margin (+5 in a rivalry game)
_OT_THIRLLER_WEIGHT = 8   # OT/shootout (+5 in a rivalry game)

_STEAL_SAVES = 35
_BLOWOUT_MARGIN = 5


def _team_name(team: Any) -> str:
    return str(getattr(team, "team_name", "") or "")


def _player_index(home: Any, away: Any) -> Dict[str, Any]:
    """player id -> player, for resolving stat lines to names."""
    idx: Dict[str, Any] = {}
    for team in (home, away):
        for roster in (getattr(team, "roster", None) or [],
                       getattr(team, "ahl_roster", None) or []):
            for p in roster:
                try:
                    idx[str(getattr(p, "id", ""))] = p
                except Exception:
                    continue
    return idx


def _is_rivalry_game(home: Any, away: Any, rivalries: list) -> bool:
    try:
        hn, an = _team_name(home), _team_name(away)
        for r in rivalries or []:
            if r.get("kind") == "team_team":
                names = {r.get("a_name", ""), r.get("b_name", "")}
                if hn in names and an in names:
                    return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Incident rolls (AdvancedGameSim post-game; GameSim does these live)
# ---------------------------------------------------------------------------

def _roll_incidents(home: Any, away: Any, home_score: int, away_score: int,
                    rivalries: list, ledger: Any,
                    is_playoff: bool = False,
                    series_game: int = 0) -> Dict[str, Any]:
    """Roll fights / brawls / controversial hits for a finished game the
    engine didn't model live. Returns {"fights": int, "brawl": bool,
    "incidents": [...]}. All writes go through record_game_incident()."""
    out: Dict[str, Any] = {"fights": 0, "brawl": False, "incidents": []}
    try:
        from reputation_system import (game_tension, fight_probability,
                                       brawl_probability,
                                       record_game_incident)
    except Exception:
        return out

    try:
        tension = float(game_tension(home, away, rivalries or [],
                                     is_playoff=is_playoff,
                                     series_game=series_game))
    except Exception:
        tension = 10.0

    margin = abs(home_score - away_score)

    # Fights: Poisson-ish count around the per-game probability. The count
    # feeds the hollow-overhype grader. Fights alone are NOT stored --
    # they're common (~0.26/game league-wide); only true line brawls earn
    # a place in the rivalry record (rolled below).
    try:
        p_fight = float(fight_probability(tension, is_playoff=is_playoff))
        lam = max(0.0, p_fight) * 1.15
        # Knuth's Poisson sampler, capped -- cheap at these lambdas.
        _l = 2.718281828 ** (-lam)
        _k, _p = 0, 1.0
        while _p > _l and _k < 8:
            _k += 1
            _p *= random.random()
        out["fights"] = max(0, _k - 1)
    except Exception:
        pass

    # Line brawl: the rarest script in hockey. Needs real heat AND the
    # classic script (blowout / late / flashpoint) -- the probability
    # function already encodes all of it.
    try:
        p_brawl = float(brawl_probability(
            tension, is_playoff=is_playoff,
            blowout=margin >= 4, period=3))
        if random.random() < p_brawl:
            record_game_incident(rivalries, home, away, "brawl",
                                 "line brawl")
            out["brawl"] = True
            out["incidents"].append("line_brawl")
    except Exception:
        pass

    # Controversial hit: under 1% of games, scaled by tension. No injury
    # invented -- the engines own injuries; this is just bad blood.
    try:
        p_hit = 0.004 * (0.5 + 2.0 * (tension / 100.0))
        if is_playoff:
            p_hit *= 1.25
        if random.random() < p_hit:
            record_game_incident(rivalries, home, away, "controversial_hit",
                                 "borderline hit under review")
            out["incidents"].append("controversial_hit")
    except Exception:
        pass

    return out


# ---------------------------------------------------------------------------
# Game stories (both engines -- the nights the season is remembered for)
# ---------------------------------------------------------------------------

def _detect_hat_tricks(sim: Any, idx: Dict[str, Any]) -> List[Dict[str, Any]]:
    found = []
    try:
        stats = getattr(sim, "stats", None) or {}
        for team_name, players in stats.items():
            for pid, line in (players or {}).items():
                try:
                    goals = int((line or {}).get("goals", 0) or 0)
                except Exception:
                    goals = 0
                if goals >= 3:
                    p = idx.get(str(pid))
                    found.append({
                        "player": getattr(p, "full_name", "Unknown"),
                        "team": team_name,
                        "goals": goals,
                    })
    except Exception:
        pass
    return found


def _detect_goalie_stories(sim: Any, home: Any, away: Any,
                           home_score: int, away_score: int,
                           idx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Shutouts + steals (35+ saves in a win)."""
    found = []
    try:
        stats = getattr(sim, "stats", None) or {}
        for team, opp_score in ((home, away_score), (away, home_score)):
            tname = _team_name(team)
            lines = stats.get(tname, None) or {}
            for pid, line in lines.items():
                try:
                    saves = int((line or {}).get("saves", 0) or 0)
                except Exception:
                    saves = 0
                if saves <= 0:
                    continue
                p = idx.get(str(pid))
                pname = getattr(p, "full_name", "Unknown")
                if opp_score == 0:
                    found.append({"kind": "shutout", "player": pname,
                                  "team": tname, "saves": saves})
                elif saves >= _STEAL_SAVES:
                    # Steal: big save night AND his team won.
                    won = ((team is home and home_score > away_score)
                           or (team is away and away_score > home_score))
                    if won:
                        found.append({"kind": "steal", "player": pname,
                                      "team": tname, "saves": saves})
    except Exception:
        pass
    return found


def record_stories(home: Any, away: Any, home_score: int, away_score: int,
                   went_ot: bool, shootout: bool, sim: Any,
                   rivalries: list, ledger: Any) -> List[Dict[str, Any]]:
    """Record the night's stories to the ledger. Returns story specs the
    caller may turn into headlines (user-involved games only)."""
    stories: List[Dict[str, Any]] = []
    if ledger is None:
        return stories
    hn, an = _team_name(home), _team_name(away)
    rivalry_game = _is_rivalry_game(home, away, rivalries)
    idx = _player_index(home, away)

    def _rec(kind: str, weight: int, text: str,
             facts: Optional[Dict[str, Any]] = None) -> None:
        try:
            ledger.record(kind, teams=[hn, an], weight=weight,
                          facts=facts or {}, text=text)
            stories.append({"kind": kind, "text": text,
                            "home": hn, "away": an,
                            "involved": (hn, an)})
        except Exception:
            pass

    # Hat tricks.
    for ht in _detect_hat_tricks(sim, idx):
        _rec("hat_trick", _HAT_TRICK_WEIGHT,
             f"{ht['player']} ({ht['team']}) scored {ht['goals']} "
             f"in a {home_score}-{away_score} "
             f"{'win' if (ht['team'] == hn) == (home_score > away_score) else 'loss'} "
             f"over {an if ht['team'] == hn else hn}.",
             {"player": ht["player"], "goals": ht["goals"],
              "score": f"{home_score}-{away_score}"})

    # Goalie stories.
    for gs in _detect_goalie_stories(sim, home, away, home_score,
                                     away_score, idx):
        if gs["kind"] == "shutout":
            _rec("shutout", _SHUTOUT_WEIGHT,
                 f"{gs['player']} ({gs['team']}) stopped all {gs['saves']} "
                 f"shots in a {home_score}-{away_score} win.",
                 {"player": gs["player"], "saves": gs["saves"]})
        else:
            _rec("goalie_steal", _STEAL_WEIGHT,
                 f"{gs['player']} ({gs['team']}) made {gs['saves']} saves "
                 f"to steal a {home_score}-{away_score} win.",
                 {"player": gs["player"], "saves": gs["saves"]})

    # Statement blowout.
    margin = abs(home_score - away_score)
    if margin >= _BLOWOUT_MARGIN:
        winner = hn if home_score > away_score else an
        w = _BLOWOUT_WEIGHT + (5 if rivalry_game else 0)
        _rec("blowout", w,
             f"{winner} humiliated "
             f"{an if winner == hn else hn} {max(home_score, away_score)}-"
             f"{min(home_score, away_score)}"
             f"{' -- in a rivalry game' if rivalry_game else ''}.",
             {"margin": margin, "rivalry": rivalry_game})

    # OT thriller.
    if went_ot or shootout:
        winner = hn if home_score > away_score else an
        w = _OT_THIRLLER_WEIGHT + (5 if rivalry_game else 0)
        how = "a shootout" if shootout else "overtime"
        _rec("ot_thriller", w,
             f"{winner} edged {an if winner == hn else hn} "
             f"{home_score}-{away_score} in {how}"
             f"{' -- a rivalry classic' if rivalry_game else ''}.",
             {"shootout": bool(shootout), "rivalry": rivalry_game})

    return stories


# ---------------------------------------------------------------------------
# Per-player career game log ("big nights")
# ---------------------------------------------------------------------------
# A kid's huge night shouldn't be forgotten when he's sent down as the
# next man up or packaged at the deadline. career_moments lives on the
# Player (plain dicts -- save/load safe), capped at 20 entries and pruned
# by significance. Only genuinely significant single games qualify:
# hat tricks, 4+ point nights, shutouts, 40-save nights, 35+ save steals.
# Playoff games rank higher. One moment per player per game (best wins).

_MOMENT_CAP = 20

_MOMENT_KINDS = {
    # kind: (label, significance)
    "hat_trick": ("Hat trick", 40),
    "four_point": ("4-point night", 35),
    "five_point": ("5-point night", 50),
    "shutout": ("Shutout", 30),
    "forty_saves": ("40-save night", 35),
    "steal": ("Stole the game", 30),
}

_PLAYOFF_BUMP = 20


def _game_lines(sim: Any, idx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize per-player game lines from either engine.

    AdvancedGameSim: sim.stats[team][pid] = {goals, assists, saves}.
    GameSim: sim.game_stats[pid] = {g, a, player}."""
    lines: List[Dict[str, Any]] = []
    try:
        stats = getattr(sim, "stats", None)
        if stats:
            for team_name, players in stats.items():
                for pid, line in (players or {}).items():
                    p = idx.get(str(pid))
                    if p is None:
                        continue
                    lines.append({
                        "player": p,
                        "team_name": team_name,
                        "goals": int((line or {}).get("goals", 0) or 0),
                        "assists": int((line or {}).get("assists", 0) or 0),
                        "saves": int((line or {}).get("saves", 0) or 0),
                    })
            return lines
    except Exception:
        pass
    try:
        gstats = getattr(sim, "game_stats", None) or {}
        for pid, st in gstats.items():
            p = (st or {}).get("player") or idx.get(str(pid))
            if p is None:
                continue
            lines.append({
                "player": p,
                "team_name": getattr(p, "team_name", ""),
                "goals": int((st or {}).get("g", 0) or 0),
                "assists": int((st or {}).get("a", 0) or 0),
                "saves": 0,  # GameSim goalie saves aren't per-game here
            })
    except Exception:
        pass
    return lines


def _is_goalie(player: Any) -> bool:
    try:
        pos = getattr(player, "primary_position", None)
        return getattr(pos, "name", "") == "GOALIE"
    except Exception:
        return False


def log_player_moments(sim: Any, home: Any, away: Any,
                       home_score: int, away_score: int,
                       game_date: Any = None,
                       is_playoff: bool = False) -> int:
    """Append career moments to the players who earned them. Returns the
    number of moments logged. Bounded, significant-only, never raises."""
    logged = 0
    try:
        idx = _player_index(home, away)
        hn, an = _team_name(home), _team_name(away)
        try:
            dstr = game_date.isoformat() if hasattr(game_date, "isoformat") \
                else str(game_date or "")
        except Exception:
            dstr = ""
        for line in _game_lines(sim, idx):
            p = line["player"]
            goals, assists, saves = line["goals"], line["assists"], line["saves"]
            points = goals + assists
            pteam = line.get("team_name") or hn
            # Fallback: resolve side via roster membership.
            if pteam not in (hn, an):
                try:
                    if p in (getattr(home, "roster", None) or []):
                        pteam = hn
                    elif p in (getattr(away, "roster", None) or []):
                        pteam = an
                    else:
                        pteam = hn
                except Exception:
                    pteam = hn
            opp = an if pteam == hn else hn
            pscore = home_score if pteam == hn else away_score
            oscore = away_score if pteam == hn else home_score
            result = "W" if pscore > oscore else ("L" if pscore < oscore else "T")
            scoreline = f"{pscore}-{oscore} {result}"

            kind = None
            detail = ""
            if _is_goalie(p):
                if saves <= 0:
                    continue
                if oscore == 0:
                    kind = "shutout"
                    detail = f"{saves} saves vs {opp} ({scoreline})"
                elif saves >= 40:
                    kind = "forty_saves"
                    detail = f"{saves} saves vs {opp} ({scoreline})"
                elif saves >= 35 and pscore > oscore:
                    kind = "steal"
                    detail = f"{saves} saves vs {opp} ({scoreline})"
            else:
                if points >= 5:
                    kind = "five_point"
                    detail = f"{goals} G, {assists} A vs {opp} ({scoreline})"
                elif goals >= 3:
                    kind = "hat_trick"
                    detail = (f"{goals} G" + (f", {assists} A" if assists else "")
                              + f" vs {opp} ({scoreline})")
                elif points >= 4:
                    kind = "four_point"
                    detail = f"{goals} G, {assists} A vs {opp} ({scoreline})"
            if kind is None:
                continue
            label, sig = _MOMENT_KINDS[kind]
            if is_playoff:
                sig += _PLAYOFF_BUMP
            moments = getattr(p, "career_moments", None)
            if not isinstance(moments, list):
                try:
                    p.career_moments = moments = []
                except Exception:
                    continue
            # One moment per player per game: keep the best.
            if any(m.get("date") == dstr and m.get("kind") == kind
                   for m in moments if isinstance(m, dict)):
                continue
            moments.append({
                "date": dstr, "kind": kind, "label": label,
                "detail": detail, "opp": opp, "score": scoreline,
                "playoff": bool(is_playoff), "sig": sig,
            })
            # Prune to the cap: lowest significance first, then oldest.
            if len(moments) > _MOMENT_CAP:
                moments.sort(key=lambda m: (
                    m.get("sig", 0) if isinstance(m, dict) else 0,
                    m.get("date", "") if isinstance(m, dict) else ""))
                del moments[0:len(moments) - _MOMENT_CAP]
                # Keep newest-first for display.
                moments.sort(key=lambda m: m.get("date", "")
                             if isinstance(m, dict) else "",
                             reverse=True)
            logged += 1
    except Exception:
        pass
    return logged


def process_postgame(sim: Any, home: Any, away: Any,
                     home_score: int, away_score: int,
                     went_ot: bool = False, shootout: bool = False,
                     rivalries: Optional[list] = None,
                     ledger: Any = None,
                     is_playoff: bool = False, series_game: int = 0,
                     roll_incidents: bool = True,
                     game_date: Any = None,
                     season_year: Any = None) -> Dict[str, Any]:
    """One call per finished game. Rolls incidents (quick-sim only --
    GameSim models them live), records game stories (both engines), and
    logs career moments to the players who earned them.

    Returns {"fights": int, "brawl": bool, "incidents": [...],
    "stories": [...], "moments": int, "iconic": bool}. Never raises;
    never touches scoring or stats.
    """
    out: Dict[str, Any] = {"fights": 0, "brawl": False,
                           "incidents": [], "stories": [], "moments": 0,
                           "iconic": False}
    rivalries = rivalries if rivalries is not None else []
    try:
        if roll_incidents:
            inc = _roll_incidents(home, away, home_score, away_score,
                                  rivalries, ledger,
                                  is_playoff=is_playoff,
                                  series_game=series_game)
            out.update({k: inc.get(k, out[k])
                        for k in ("fights", "brawl", "incidents")})
        out["stories"] = record_stories(home, away, home_score,
                                        away_score, went_ot, shootout,
                                        sim, rivalries, ledger)
        out["moments"] = log_player_moments(sim, home, away, home_score,
                                            away_score, game_date=game_date,
                                            is_playoff=is_playoff)
        # Iconic games: the nights the franchise remembers. Detection
        # reuses the same game data -- a few integer comparisons, no
        # extra sim pass. Records on both clubs + the stars' logs.
        try:
            from iconic_games import detect_and_record
            _icon = detect_and_record(
                home, away, home_score, away_score, sim,
                went_ot=went_ot, shootout=shootout,
                rivalries=rivalries, is_playoff=is_playoff,
                series_game=series_game, brawl=out.get("brawl", False),
                game_date=game_date, season_year=season_year)
            out["iconic"] = _icon is not None
        except Exception:
            pass
    except Exception:
        pass
    return out
