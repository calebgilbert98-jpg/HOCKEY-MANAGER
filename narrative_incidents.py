# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
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

def _pick_hit_participants(home: Any, away: Any):
    """Who threw the borderline hit and who took it. The chippier room
    supplies the hitter (its most aggressive skater); the other room
    supplies the victim. Names only -- the engines own injuries."""
    try:
        from reputation_system import _roster_chippiness
        hc = _roster_chippiness(getattr(home, "roster", []))
        ac = _roster_chippiness(getattr(away, "roster", []))
    except Exception:
        hc, ac = 30.0, 30.0
    if hc == ac:
        hitting, victim_team = (home, away) if random.random() < 0.5 else (away, home)
    else:
        hitting, victim_team = (home, away) if hc > ac else (away, home)

    def _skaters(team):
        try:
            from game_classes import PlayerPosition as _PP
            return [p for p in (getattr(team, "roster", []) or [])
                    if getattr(p, "primary_position", None) != _PP.GOALIE]
        except Exception:
            return list(getattr(team, "roster", []) or [])

    hs, vs = _skaters(hitting), _skaters(victim_team)
    hitter = (max(hs, key=lambda p: getattr(p, "aggressiveness", 50) or 50)
              if hs else None)
    victim = random.choice(vs) if vs else None
    return hitting, hitter, victim_team, victim


def _goalie_run_probability(is_playoff=False, rivalry_heat=0.0,
                            chippiness=30.0):
    """How often a controversial hit runs the goalie instead of a skater.

    Rare at base (10% of controversial hits); likelier in the playoffs,
    against heated rivals, and from chippy (high-intensity) rooms.
    Capped so it stays a flashpoint, not a pattern.
    """
    try:
        p = 0.10
        if is_playoff:
            p *= 1.5
        p *= 1.0 + max(0.0, float(rivalry_heat or 0.0)) / 150.0
        p *= 0.7 + max(0.0, float(chippiness or 0.0)) / 100.0
        return min(p, 0.35)
    except Exception:
        return 0.10


def _pick_goalie_victim(team: Any):
    """The goalie who'd be in net: best healthy goalie, else best goalie.

    Used by the goalie-run variant -- the victim is whoever is actually
    minding the net, never a placeholder. Returns None when the roster
    has no goalie at all.
    """
    try:
        from game_classes import PlayerPosition as _PP
        gs = [p for p in (getattr(team, "roster", []) or [])
              if getattr(p, "primary_position", None) == _PP.GOALIE]
        if not gs:
            return None
        healthy = [p for p in gs if not getattr(p, "is_injured", False)]
        pool = healthy or gs

        def _ovr(g):
            try:
                return float(g.overall_rating()) if callable(
                    getattr(g, "overall_rating", None)) else 0.0
            except Exception:
                return 0.0

        return max(pool, key=_ovr)
    except Exception:
        return None


def _roll_incidents(home: Any, away: Any, home_score: int, away_score: int,
                    rivalries: list, ledger: Any,
                    is_playoff: bool = False,
                    series_game: int = 0) -> Dict[str, Any]:
    """Roll fights / brawls / controversial hits for a finished game the
    engine didn't model live. Returns {"fights": int, "brawl": bool,
    "incidents": [...], "incident_details": [...]}. All writes go through
    record_game_incident()."""
    out: Dict[str, Any] = {"fights": 0, "brawl": False,
                           "incidents": [], "incident_details": []}
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
    # feeds the hollow-overhype grader. W5: fights ARE stored now -- one
    # incident per game with at least one fight (not one per fight; they're
    # common at ~0.26/game league-wide) -- so they feed the rivalry store's
    # long-term memory and the grudge floors, like the live engine's.
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
        if out["fights"] > 0:
            from reputation_system import feed_grudge as _fg
            record_game_incident(
                rivalries, home, away, "fight",
                f"{out['fights']} fight(s) -- {home_score}-{away_score} final")
            try:
                _fg(rivalries, home, away, grudge=2)
            except Exception:
                pass
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
            out["incident_details"].append({
                "kind": "line_brawl",
                "home": _team_name(home), "away": _team_name(away),
                "home_score": home_score, "away_score": away_score,
            })
    except Exception:
        pass

    # Controversial hit: under 1% of games, scaled by tension. No injury
    # invented -- the engines own injuries; this is just bad blood. The
    # detail names the hitter and the victim so the consequence pass
    # (DoPS review, press, morale) has a story to tell.
    try:
        p_hit = 0.004 * (0.5 + 2.0 * (tension / 100.0))
        if is_playoff:
            p_hit *= 1.25
        if random.random() < p_hit:
            _ht, _hp, _vt, _vp = _pick_hit_participants(home, away)
            # Goalie-run variant (additive): rarely the borderline hit runs
            # the opposing goalie instead of a skater -- the hitter is
            # always a skater, goalies don't throw these hits. Rare at
            # base; likelier in the playoffs, against heated rivals, and
            # from chippy (high-intensity) rooms. The goalie's injury
            # state still comes from the engines (never invented), which
            # the DoPS review already reads for its escalators.
            _goalie_run = False
            try:
                try:
                    from reputation_system import \
                        get_rivalry_heat as _gr_heat
                    _rh = _gr_heat(rivalries, _ht, _vt)
                except Exception:
                    _rh = 0.0
                try:
                    from reputation_system import \
                        _roster_chippiness as _gr_chip
                    _chip = _gr_chip(getattr(_ht, "roster", []))
                except Exception:
                    _chip = 30.0
                _p_gr = _goalie_run_probability(is_playoff, _rh, _chip)
                if random.random() < _p_gr:
                    _gv = _pick_goalie_victim(_vt)
                    if _gv is not None:
                        _vp = _gv
                        _goalie_run = True
            except Exception:
                _goalie_run = False
            _hn = getattr(_hp, "full_name", "A hitter") if _hp else "A hitter"
            _vn = getattr(_vp, "full_name", "a victim") if _vp else "a victim"
            _htn, _vtn = _team_name(_ht), _team_name(_vt)
            if _goalie_run:
                _detail = (f"{_hn} ({_htn}) ran {_vtn} goalie {_vn} -- "
                           f"under league review")
            else:
                _detail = (f"{_hn} ({_htn}) caught {_vn} ({_vtn}) with a "
                           f"borderline hit -- under league review")
            record_game_incident(
                rivalries, home, away, "controversial_hit", _detail)
            out["incidents"].append("controversial_hit")
            # The hitter's controversy (original personality parameter,
            # dealt at generation) travels with the detail so the DoPS
            # fine chance scales off who he is, not a flat league rate.
            try:
                _hcon = float(getattr(_hp, "controversy",
                                      getattr(_hp, "base_controversy", 30))
                              or 30) if _hp else 30.0
            except Exception:
                _hcon = 30.0
            out["incident_details"].append({
                "kind": "controversial_hit",
                "hitter": _hn, "hitter_team": _htn,
                "victim": _vn, "victim_team": _vtn,
                "hitter_controversy": max(0.0, min(100.0, _hcon)),
                "goalie_run": bool(_goalie_run),
            })
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
                        "player_obj": p,  # clutch epithet resolution
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
                                  "player_obj": p,  # clutch epithet
                                  "team": tname, "saves": saves})
                elif saves >= _STEAL_SAVES:
                    # Steal: big save night AND his team won.
                    won = ((team is home and home_score > away_score)
                           or (team is away and away_score > home_score))
                    if won:
                        found.append({"kind": "steal", "player": pname,
                                      "player_obj": p,  # clutch epithet
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
             facts: Optional[Dict[str, Any]] = None,
             player: Any = None) -> None:
        """Record a story to the ledger and queue its headline spec.

        player (additive): the story's subject -- when he holds a clutch
        tag, its epithet travels on the SPEC (not the ledger text, which
        stays a clean fact record) so headlines.py can color the story.
        """
        try:
            ledger.record(kind, teams=[hn, an], weight=weight,
                          facts=facts or {}, text=text)
            _spec: Dict[str, Any] = {"kind": kind, "text": text,
                                     "home": hn, "away": an,
                                     "involved": (hn, an)}
            try:
                from clutch import clutch_epithet as _cep_st
                _ep = _cep_st(player) if player is not None else ""
                if _ep:
                    _spec["epithet"] = _ep
            except Exception:
                pass
            stories.append(_spec)
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
              "score": f"{home_score}-{away_score}"},
             player=ht.get("player_obj"))

    # Goalie stories.
    for gs in _detect_goalie_stories(sim, home, away, home_score,
                                     away_score, idx):
        if gs["kind"] == "shutout":
            _rec("shutout", _SHUTOUT_WEIGHT,
                 f"{gs['player']} ({gs['team']}) stopped all {gs['saves']} "
                 f"shots in a {home_score}-{away_score} win.",
                 {"player": gs["player"], "saves": gs["saves"]},
                 player=gs.get("player_obj"))
        else:
            _rec("goalie_steal", _STEAL_WEIGHT,
                 f"{gs['player']} ({gs['team']}) made {gs['saves']} saves "
                 f"to steal a {home_score}-{away_score} win.",
                 {"player": gs["player"], "saves": gs["saves"]},
                 player=gs.get("player_obj"))

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
                           "incidents": [], "incident_details": [],
                           "stories": [], "moments": 0, "iconic": False}
    rivalries = rivalries if rivalries is not None else []
    try:
        if roll_incidents:
            inc = _roll_incidents(home, away, home_score, away_score,
                                  rivalries, ledger,
                                  is_playoff=is_playoff,
                                  series_game=series_game)
            out.update({k: inc.get(k, out[k])
                        for k in ("fights", "brawl", "incidents",
                                  "incident_details")})
        # GameSim models incidents live instead of rolling them: surface
        # its brawl flag so iconic-games detection and the consequence
        # pass see the same truth the quick path reports.
        if getattr(sim, "_brawl_happened", False):
            out["brawl"] = True
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


# ---------------------------------------------------------------------------
# Incident consequences -- the drama layer's shared aftermath.
# ---------------------------------------------------------------------------
# One consumer per game (called from _narrative_postgame), fed only by
# rolled incidents -- GameSim applies its own live consequences inline and
# never lands here, so neither engine can double-fire. Turns a recorded
# incident into: a league headline, a DoPS fine, room morale, and a press
# hook. Rivalry heat flows through the original wound mechanism --
# record_game_incident() logs the incident on the team_team record with the
# original INCIDENT_WEIGHTS, and game_tension_breakdown() heats the next
# meeting from those wounds (weight * 0.75^games_ago). No new heat numbers
# here. Never raises; never touches scoring or stats.


def _find_player(team: Any, name: str):
    for p in (getattr(team, "roster", None) or []):
        if getattr(p, "full_name", "") == name:
            return p
    return None


def _prior_suspensions(player: Any) -> int:
    """Repeat-offender count from the existing controversy_history."""
    try:
        hist = getattr(player, "controversy_history", None) or []
        return sum(1 for e in hist
                   if isinstance(e, dict) and e.get("type") == "suspension")
    except Exception:
        return 0


def _scrub_suspended_from_lineup(team: Any) -> int:
    """Pull suspended skaters out of a team's dressed lineup.

    Replaces each suspended player's nested-line slots with the best
    available skater (not injured, not suspended, not already dressed)
    from the same position group, then refreshes the flat keys via
    flatten_lineup. Returns the number of slots fixed. Never raises --
    a missing replacement leaves the slot rather than crashing.
    """
    fixed = 0
    try:
        from quick_sim import flatten_lineup
        from game_classes import PlayerPosition as _PP
        lineup = getattr(team, "lineup", None)
        if not isinstance(lineup, dict):
            return 0
        roster = getattr(team, "roster", None) or []
        dressed = set()
        for _grp in ("Forwards", "Defense"):
            for _line in (lineup.get(_grp) or []):
                for _p in (_line or []):
                    if _p is not None:
                        dressed.add(id(_p))
        _FWD = {_PP.LEFT_WING, _PP.CENTER, _PP.RIGHT_WING}
        _DEF = {_PP.LEFT_DEFENSE, _PP.RIGHT_DEFENSE, _PP.DEFENSE}

        def _pool(pos_group):
            cands = [p for p in roster
                     if getattr(p, "primary_position", None) in pos_group
                     and not getattr(p, "is_injured", False)
                     and not (getattr(p, "suspension_games_remaining", 0)
                              or 0)
                     and id(p) not in dressed]
            try:
                cands.sort(key=lambda p: p.overall_rating(), reverse=True)
            except Exception:
                pass
            return cands

        _fwd_pool, _def_pool = _pool(_FWD), _pool(_DEF)

        def _swap(_line, _idx, _pool_list):
            nonlocal fixed
            try:
                _p = _line[_idx] if _idx < len(_line) else None
            except Exception:
                _p = None
            if _p is None or not (getattr(
                    _p, "suspension_games_remaining", 0) or 0):
                return
            if _pool_list:
                _rep = _pool_list.pop(0)
                _line[_idx] = _rep
                dressed.add(id(_rep))
                fixed += 1

        for _line in (lineup.get("Forwards") or []):
            if isinstance(_line, list):
                for _i in range(min(3, len(_line))):
                    _swap(_line, _i, _fwd_pool)
        for _pair in (lineup.get("Defense") or []):
            if isinstance(_pair, list):
                for _i in range(min(2, len(_pair))):
                    _swap(_pair, _i, _def_pool)
        if fixed:
            try:
                flatten_lineup(lineup)
            except Exception:
                pass
    except Exception:
        pass
    return fixed


def _dops_suspension_review(app: Any, d: dict, hitter_team: Any,
                            victim_team: Any, game_date: Any,
                            involved) -> dict:
    """One DoPS review decision for a controversial hit.

    Returns {"games": N} (N > 0 suspended) or {"games": 0}. Every input
    is an original parameter: the hitter's dealt personality attributes
    (discipline / aggressiveness / controversy), the victim's post-game
    state (the engines own injuries -- never invented here), star status
    on the native 100-point scale, and repeat-offender history from
    controversy_history. On a suspension the player attributes are set
    (served in team games, starting with the NEXT one), the history is
    appended via record_controversy_event, a league headline goes out,
    and the team's dressed lineup is scrubbed. Never raises.
    """
    try:
        hitter_name = d.get("hitter", "") or ""
        victim_name = d.get("victim", "") or ""
        hitter = _find_player(hitter_team, hitter_name)
        if hitter is None:
            return {"games": 0}
        victim = _find_player(victim_team, victim_name)
        try:
            _disc = float(getattr(hitter, "discipline", 50) or 50)
        except Exception:
            _disc = 50.0
        try:
            _aggr = float(getattr(hitter, "aggressiveness", 50) or 50)
        except Exception:
            _aggr = 50.0
        try:
            _contr = float(d.get("hitter_controversy", 30) or 30)
        except Exception:
            _contr = 30.0
        _contr = max(0.0, min(100.0, _contr))
        dirt = max(0.0, min(1.0,
                            (_aggr + (100.0 - _disc) + _contr) / 300.0))
        victim_injured = (bool(getattr(victim, "is_injured", False))
                          if victim is not None else False)
        try:
            star_victim = bool(victim is not None
                               and victim.overall_rating() >= 90)
        except Exception:
            star_victim = False
        prior = _prior_suspensions(hitter)
        p = (0.08 + 0.30 * dirt
             + (0.12 if victim_injured else 0.0)
             + (0.06 if star_victim else 0.0)
             + 0.08 * min(prior, 2))
        p = min(p, 0.85)
        if random.random() >= p:
            return {"games": 0}
        games = 1
        if victim_injured:
            games += 1
        if star_victim:
            games += 1
        if _disc < 30:
            games += 1
        games += 2 * min(prior, 3)
        games = min(games, 10)
        hitter.suspension_games_remaining = games
        hitter.suspension_reason = f"Illegal hit on {victim_name}"
        hitter.suspended_today = True
        try:
            from reputation_system import record_controversy_event
            _gd = (str(game_date) if game_date is not None else None)
            record_controversy_event(
                hitter, "suspension", min(10, 3 + games),
                f"Suspended {games} games for an illegal hit on "
                f"{victim_name}", game_date=_gd)
        except Exception:
            pass
        try:
            import headlines as _hl
            _hl.deliver_spec(app, {
                "kind": "suspension",
                "name": hitter_name,
                "team": getattr(hitter_team, "team_name", ""),
                "games": games,
                "victim": victim_name,
                "involved": involved,
            })
        except Exception:
            pass
        try:
            _scrub_suspended_from_lineup(hitter_team)
        except Exception:
            pass
        return {"games": games}
    except Exception:
        return {"games": 0}


def apply_incident_consequences(app: Any, home: Any, away: Any,
                                incidents: list, incident_details: list,
                                brawl: bool, scores, game_date: Any,
                                user_team: Any, rivalries: list) -> list:
    """Shared aftermath for one finished game. Returns the drama dicts
    stashed on both clubs for the press (also returned for QA)."""
    drama = []
    try:
        from reputation_system import record_team_event
    except Exception:
        return drama
    try:
        import headlines as _hl
    except Exception:
        _hl = None

    home_score, away_score = int(scores[0]), int(scores[1])
    details = {d.get("kind"): d for d in (incident_details or [])
               if isinstance(d, dict)}

    def _involved():
        names = set()
        if user_team is not None:
            names.add(getattr(user_team, "team_name", ""))
        return (getattr(home, "team_name", ""), getattr(away, "team_name", ""))

    # -- Line brawl ------------------------------------------------------
    # Rivalry heat: the brawl was already logged on the team_team record by
    # _roll_incidents (kind "brawl", original INCIDENT_WEIGHTS) -- the
    # wound mechanism heats the rematch, no extra bump here.
    if "line_brawl" in (incidents or []):
        d = details.get("line_brawl", {})
        if _hl is not None:
            try:
                _hl.deliver_spec(app, {
                    "kind": "line_brawl_quick",
                    "home": _team_name(home), "away": _team_name(away),
                    "home_score": home_score, "away_score": away_score,
                    "involved": _involved(),
                })
            except Exception:
                pass
        # Both rooms come out of a brawl bonded: us-against-the-world.
        try:
            record_team_event(
                home, "line_brawl",
                f"Line brawl vs {_team_name(away)} -- the room answered "
                f"the bell together.", morale_delta=1, tone="up")
            record_team_event(
                away, "line_brawl",
                f"Line brawl at {_team_name(home)} -- nobody backed down.",
                morale_delta=1, tone="up")
        except Exception:
            pass
        # D4: your club in a line brawl is a board-level scandal
        # (scandal fuel) -- the room is bonded, the owners are furious.
        try:
            _utn = (getattr(user_team, "team_name", "")
                    if user_team is not None else "")
            if _utn and _utn in (_team_name(home), _team_name(away)):
                import reputation_system as _rs4b
                _rs4b.note_scandal(
                    getattr(getattr(app, "career", None), "board", None))
        except Exception:
            pass
        drama.append({"kind": "line_brawl", "live": False,
                      "home": _team_name(home), "away": _team_name(away),
                      "home_score": home_score, "away_score": away_score})

    # -- Controversial hit -----------------------------------------------
    # Rivalry heat: already logged by _roll_incidents (kind
    # "controversial_hit", original INCIDENT_WEIGHTS) -- the wound
    # mechanism heats the rematch, no extra bump here.
    if "controversial_hit" in (incidents or []):
        d = details.get("controversial_hit", {})
        hitter_team_name = d.get("hitter_team", "")
        victim_team_name = d.get("victim_team", "")
        hitter_team = home if _team_name(home) == hitter_team_name else away
        victim_team = away if hitter_team is home else home
        hitter, victim = d.get("hitter", "A hitter"), d.get("victim", "a victim")
        # DoPS review: ONE decision, two possible punishments. A suspension
        # keeps the player out of the lineup for team games served (the
        # review scales off the original parameters -- the hitter's dealt
        # personality attributes, the victim's state, and repeat-offender
        # history). If no suspension, the wallet gets lighter instead --
        # the existing fine path, untouched. $5,000 is the NHL CBA maximum.
        _review = _dops_suspension_review(
            app, d, hitter_team, victim_team, game_date, _involved())
        suspended_games = int(_review.get("games", 0) or 0)
        fined = False
        if suspended_games <= 0:
            # Grounded in the original personality model: the hitter's
            # controversy attribute (dealt at generation from discipline /
            # composure / aggressiveness / teamwork) drives the fine chance --
            # hotheads draw the league's eye.
            try:
                _hc = float(d.get("hitter_controversy", 30) or 0)
            except Exception:
                _hc = 30.0
            _hc = max(0.0, min(100.0, _hc))
            fined = random.random() < 0.15 + 0.55 * (_hc / 100.0)
            if fined and _hl is not None:
                amount = 5000
                try:
                    _hl.deliver_spec(app, {
                        "kind": "media_fine", "name": hitter,
                        "team": hitter_team_name, "amount": amount,
                        "reason": f"the borderline hit on {victim}",
                        "involved": _involved(),
                    })
                    lg = getattr(app, "league", None)
                    if lg is not None:
                        mf = getattr(lg, "media_fines", None)
                        if isinstance(mf, list):
                            mf.append({"date": str(game_date), "name": hitter,
                                       "team": hitter_team_name, "amount": amount,
                                       "reason": "borderline hit"})
                except Exception:
                    pass
        try:
            _grun = bool(d.get("goalie_run"))
            _hit_phrase = (f"ran {victim} (their goalie)" if _grun
                           else f"caught {victim} with a borderline hit")
            record_team_event(
                victim_team, "controversial_hit",
                f"Seething: {hitter} ({hitter_team_name}) {_hit_phrase}"
                f"{f' and was suspended {suspended_games} games' if suspended_games else (' and was fined' if fined else '')} "
                f"-- the room wants payback.",
                morale_delta=-1, tone="down")
            record_team_event(
                hitter_team, "controversial_hit",
                f"Rallying around {hitter} after the DoPS review -- "
                f"{f'suspended {suspended_games} games' if suspended_games else ('fined' if fined else 'no supplemental discipline')}.",
                morale_delta=1, tone="up")
        except Exception:
            pass
        # D4: YOUR player getting suspended is a board-level scandal
        # (scandal fuel). The review itself stays user-blind (parity);
        # the headline is applied here, at the aftermath layer.
        try:
            _utn4 = (getattr(user_team, "team_name", "")
                     if user_team is not None else "")
            if (suspended_games > 0 and _utn4
                    and hitter_team_name == _utn4):
                import reputation_system as _rs4s
                _rs4s.note_scandal(
                    getattr(getattr(app, "career", None), "board", None))
        except Exception:
            pass
        drama.append({"kind": "controversial_hit", "live": False,
                      "hitter": hitter, "hitter_team": hitter_team_name,
                      "victim": victim, "victim_team": victim_team_name,
                      "fined": fined, "suspended": suspended_games})

    # -- Live-brawl press hook (GameSim did its own consequences) ---------
    # The live brawl already called record_game_incident(kind "brawl") in
    # simulation._run_brawl -- the wound mechanism heats the rematch.
    if brawl and "line_brawl" not in (incidents or []):
        drama.append({"kind": "line_brawl", "live": True,
                      "home": _team_name(home), "away": _team_name(away),
                      "home_score": home_score, "away_score": away_score})
        # D4: your club in a live GameSim brawl is a board-level scandal
        # (scandal fuel), same as the rolled-brawl path above.
        try:
            _utn4b = (getattr(user_team, "team_name", "")
                      if user_team is not None else "")
            if _utn4b and _utn4b in (_team_name(home), _team_name(away)):
                import reputation_system as _rs4b
                _rs4b.note_scandal(
                    getattr(getattr(app, "career", None), "board", None))
        except Exception:
            pass

    # Stash for the press: the post-match presser reads the club's most
    # recent drama and asks about it.
    try:
        for team in (home, away):
            team._recent_drama = list(drama)
    except Exception:
        pass
    return drama


# ---------------------------------------------------------------------------
# Item 4: DoPS review for full-detail GameSim games' live borderline hits
# ---------------------------------------------------------------------------
# The rolled path above only fires for quick-sim games (roll_incidents).
# GameSim records its borderline hits live on the sim (controversy_system
# stashes a d-dict per hit); this hook replays each through the SAME
# shared aftermath -- the one suspension-or-fine decision plus its
# existing consequences (headline, media fine ledger, room morale, press
# stash). Rivalry heat is NOT re-applied: the live hit already logged its
# wound via _rivalry_incident at hit time, exactly as the rolled path's
# comment notes for _roll_incidents. The stash is consumed once per game
# (cleared before iterating), so a repeated hook call cannot double-fire.
# Never raises; never touches scoring, stats, or any tuning constant.


def apply_live_dops_reviews(app: Any, sim_engine: Any, home_team: Any,
                           away_team: Any, scores, game_date: Any,
                           user_team: Any, rivalries: list) -> list:
    """Run each live borderline hit through the DoPS decision. Returns the
    drama dicts (with kind "controversial_hit" marked live=True)."""
    drama = []
    try:
        hits = getattr(sim_engine, "_live_borderline_hits", None)
        if not hits:
            return drama
        # Consume once: clear before iterating so re-entry is a no-op.
        try:
            sim_engine._live_borderline_hits = []
        except Exception:
            pass
        for d in list(hits):
            if not isinstance(d, dict) or d.get("kind") != "controversial_hit":
                continue
            try:
                res = apply_incident_consequences(
                    app, home_team, away_team,
                    ["controversial_hit"], [dict(d)], False,
                    (int(scores[0]), int(scores[1])),
                    game_date, user_team, rivalries)
                if isinstance(res, list):
                    for _rd in res:
                        if (isinstance(_rd, dict)
                                and _rd.get("kind") == "controversial_hit"):
                            _rd["live"] = True
                    drama.extend(res)
            except Exception:
                pass
    except Exception:
        pass
    return drama
