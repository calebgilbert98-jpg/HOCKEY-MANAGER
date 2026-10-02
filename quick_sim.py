# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""quick_sim.py -- the fast ("quick") simulation engine.

Extracted verbatim from main.py (2026-09-28) to shrink the main.py god-file,
the #1 merge-collision surface for two parallel developers. No logic changed.

Contents:
  roll_game_injury / best_lines / flatten_lineup -- lineup helpers shared with
      the GUI (re-exported through main.py, so `from main import best_lines`
      keeps working).
  AdvancedGameSim -- the quick-sim engine used for AI-vs-AI games and the
      user's Quick Sim choice (~95% of simmed games). Takes a GameManager at
      construction; has no dependency on main.py itself.

Ownership: the quick-sim engine. Coordinate with the tactics/mesh owners
before changing scoring-affecting code here -- balance changes must be made
in BOTH engines (see docs/TACTICS_REWORK_GUIDE.md).
"""
import math
import random
from typing import NamedTuple

from collections import deque
_SCORE_NOISE_FLOOR = 0.601856  # floor under per-game scoring noise
from game_classes import PlayerPosition

def roll_game_injury(team):
    """Roll a single in-game injury for a team (shared by detailed + batch sims).

    Delegates to injury_data.roll_general_injury -- the one shared injury
    decision (W4, icetime-ecosystem). Keeps the historical contract: exactly
    one victim is hurt per call (callers gate the per-team rate with
    injury_data.QUICK_ENGINE_GENERAL_RATE); returns the injured Player, or
    None when nobody was hurt. Severity, body-part mix, and concussion odds
    come from the grounded tables; goalies are eligible at a reduced weight.
    """
    try:
        import injury_data as _inj
    except Exception:
        return None
    # No internal gate: callers apply the per-team rate. base_prob=1.0 makes
    # the shared decision always pick a victim (random() < 1.0 always).
    victim, spec = _inj.roll_general_injury(team, base_prob=1.0)
    if victim is None:
        return None
    _inj.apply_injury(victim, spec, team)
    return victim


def best_lines(team):
    """Builds the best possible lineup for the given team based on player ratings and positions."""
    # Injured or suspended players can't dress: filter them out (fall back
    # to full group if empty)

    def _healthy(players):
        eligible = [p for p in players
                    if not getattr(p, 'is_injured', False)
                    and not (getattr(p, 'suspension_games_remaining', 0)
                             or 0)]
        return eligible if eligible else players
    # Select top 13 forwards, 8 defensemen, 2 goalies by position and rating
    forwards = _healthy([p for p in team.roster if p.primary_position in [PlayerPosition.LEFT_WING, PlayerPosition.CENTER, PlayerPosition.RIGHT_WING]])
    defensemen = _healthy([p for p in team.roster if p.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]])
    goalies = _healthy([p for p in team.roster if p.primary_position == PlayerPosition.GOALIE])

    # Sort by talent tier (Muck 2026-10-01): the AI dresses what the human
    # sees -- tier bands, not 1-point overall differences.
    try:
        from attribute_composites import talent_tier_for_player as _ttf
        from attribute_composites import tier_index as _tix
        _tkey = lambda p: _tix(_ttf(p))
    except Exception:
        _tkey = lambda p: 0
    forwards = sorted(forwards, key=_tkey)[:13]  # Changed to 13 to ensure line 4 gets players
    # NOTE: do NOT truncate defensemen here. The 3-pair loop below picks
    # position-aware; truncating to 6 first can cut a natural RD/LD and leave
    # a pair short. Keep the full healthy pool so the fallback can fill in.
    defensemen = sorted(defensemen, key=_tkey)
    goalies = sorted(goalies, key=_tkey)[:2]

    # Build forward lines
    fw_lines = []
    
    # Keep track of players already assigned to lines
    assigned_forwards = []
    
    # For first line, try to get the best players by position
    lw1 = next((p for p in forwards if p.primary_position == PlayerPosition.LEFT_WING and p not in assigned_forwards), None)
    c1 = next((p for p in forwards if p.primary_position == PlayerPosition.CENTER and p not in assigned_forwards), None)
    rw1 = next((p for p in forwards if p.primary_position == PlayerPosition.RIGHT_WING and p not in assigned_forwards), None)
    
    # If we're missing players, fill with best remaining players
    remaining_for_line1 = [p for p in forwards if p not in [lw1, c1, rw1] and p not in assigned_forwards]
    if not lw1 and remaining_for_line1:
        lw1 = remaining_for_line1.pop(0)
    if not c1 and remaining_for_line1:
        c1 = remaining_for_line1.pop(0)
    if not rw1 and remaining_for_line1:
        rw1 = remaining_for_line1.pop(0)
    
    # Mark these players as assigned
    if lw1: assigned_forwards.append(lw1)
    if c1: assigned_forwards.append(c1)
    if rw1: assigned_forwards.append(rw1)
    fw_lines.append([lw1, c1, rw1])
    
    # For the remaining 3 lines, build with best available players
    for line_num in range(1, 4):
        line = []
        for pos_type in [PlayerPosition.LEFT_WING, PlayerPosition.CENTER, PlayerPosition.RIGHT_WING]:
            # Try to get a natural fit first
            player = next((p for p in forwards if p.primary_position == pos_type and p not in assigned_forwards), None)
            
            # If no natural fit, take best available
            if not player:
                remaining = [p for p in forwards if p not in assigned_forwards]
                if remaining:
                    player = remaining[0]
            
            # Add player to line and mark as assigned
            if player:
                line.append(player)
                assigned_forwards.append(player)
            else:
                line.append(None)
        
        fw_lines.append(line)

    # Build defense pairs with natural LD/RD if possible
    def_pairs = []
    assigned_defense = []
    
    # For each pair, try to get a natural LD and RD - 3 pairs to match
    # the sim's rotation ((clock // 60) % 3) and the lines editor
    for _ in range(3):
        ld = next((p for p in defensemen if (p.primary_position == PlayerPosition.LEFT_DEFENSE or p.primary_position == PlayerPosition.DEFENSE) and p not in assigned_defense), None)
        rd = next((p for p in defensemen if (p.primary_position == PlayerPosition.RIGHT_DEFENSE or p.primary_position == PlayerPosition.DEFENSE) and p != ld and p not in assigned_defense), None)
        # Fallback: fill any unfilled slot with the best available defenseman
        # (off-side if needed -- better than skating a short pair). Mirrors
        # the forwards fallback above.
        if not ld:
            remaining = [p for p in defensemen if p not in assigned_defense and p != rd]
            if remaining:
                ld = remaining[0]
        if not rd:
            remaining = [p for p in defensemen if p not in assigned_defense and p != ld]
            if remaining:
                rd = remaining[0]

        # Mark these players as assigned
        if ld: assigned_defense.append(ld)
        if rd: assigned_defense.append(rd)
        def_pairs.append([ld, rd])
    
    # Build Power Play units
    # Use top offensive forwards and offensive defensemen
    offensive_forwards = sorted(forwards, key=lambda p: (
        getattr(p, 'offensive_awareness', 0) * 0.4 + 
        getattr(p, 'shooting', 0) * 0.3 + 
        getattr(p, 'passing', 0) * 0.3
    ), reverse=True)
    
    offensive_defensemen = sorted(defensemen, key=lambda p: (
        getattr(p, 'offensive_awareness', 0) * 0.4 + 
        getattr(p, 'shooting', 0) * 0.3 + 
        getattr(p, 'passing', 0) * 0.3
    ), reverse=True)
    
    pp1_forwards = offensive_forwards[:3] if len(offensive_forwards) >= 3 else offensive_forwards + [None] * (3 - len(offensive_forwards))
    pp2_forwards = offensive_forwards[3:6] if len(offensive_forwards) >= 6 else offensive_forwards[3:] + [None] * (3 - len(offensive_forwards[3:]))
    
    pp1_defense = offensive_defensemen[:2] if len(offensive_defensemen) >= 2 else offensive_defensemen + [None] * (2 - len(offensive_defensemen))
    pp2_defense = offensive_defensemen[2:4] if len(offensive_defensemen) >= 4 else offensive_defensemen[2:] + [None] * (2 - len(offensive_defensemen[2:]))
    
    # Build Penalty Kill units
    # Use defensively strong forwards
    defensive_forwards = sorted(forwards, key=lambda p: (
        getattr(p, 'defensive_awareness', 0) * 0.4 + 
        getattr(p, 'shot_blocking', 0) * 0.3 + 
        getattr(p, 'work_rate', 0) * 0.3
    ), reverse=True)
    
    defensive_defensemen = sorted(defensemen, key=lambda p: (
        getattr(p, 'defensive_awareness', 0) * 0.4 + 
        getattr(p, 'shot_blocking', 0) * 0.4 + 
        getattr(p, 'checking', 0) * 0.2
    ), reverse=True)
    
    pk1_forwards = defensive_forwards[:2] if len(defensive_forwards) >= 2 else defensive_forwards + [None] * (2 - len(defensive_forwards))
    pk2_forwards = defensive_forwards[2:4] if len(defensive_forwards) >= 4 else defensive_forwards[2:] + [None] * (2 - len(defensive_forwards[2:]))
    
    pk1_defense = defensive_defensemen[:2] if len(defensive_defensemen) >= 2 else defensive_defensemen + [None] * (2 - len(defensive_defensemen))
    pk2_defense = defensive_defensemen[2:4] if len(defensive_defensemen) >= 4 else defensive_defensemen[2:] + [None] * (2 - len(defensive_defensemen[2:]))

    # --- TOI-forensics repair (icetime-ecosystem, 2026-09-29) ---
    # Never emit None skater slots in the even-strength lines. A None slot
    # used to mean "the sim's per-tick fill-in dresses the best available
    # player by overall" -- genuine double-shift ice time that W3's per-tick
    # ledger recorded faithfully but W2's unit-based ledger never credited
    # (it only credits nominal slot holders), leaving the 30-min governor
    # blind: a double-shifting star could skate 32-38 min while the governor
    # saw ~18 and never bound him (found via W2/W3 ledger divergence on
    # short-benched rosters). Filling the slot explicitly with the same
    # best-available skater the fill-in would dress changes no on-ice
    # behavior -- it just makes selection, execution, and both ledgers
    # agree. Defense pairs fall back to any skater (emergency D, exactly
    # what the fill-in dressed). PP/PK units intentionally untouched (a
    # separate known seam, out of scope for this repair).
    def _repair_es_slots():
        try:
            assigned = []
            seen = set()
            use_count = {}
            for _line in fw_lines:
                for _p in (_line or []):
                    if _p is not None and id(_p) not in seen:
                        seen.add(id(_p))
                        assigned.append(_p)
                    if _p is not None:
                        use_count[id(_p)] = use_count.get(id(_p), 0) + 1
            for _pair in def_pairs:
                for _p in (_pair or []):
                    if _p is not None and id(_p) not in seen:
                        seen.add(id(_p))
                        assigned.append(_p)
                    if _p is not None:
                        use_count[id(_p)] = use_count.get(id(_p), 0) + 1
            try:
                _ovr = {}
                for _p in assigned:
                    try:
                        _ovr[id(_p)] = float(_p.overall_rating())
                    except Exception:
                        _ovr[id(_p)] = 0.0
            except Exception:
                _ovr = {}
            if not assigned:
                return

            # -- Short-bench hole fill (2026-09-30, Muck) -------------------
            # The hole is filled the way a lineup is chosen: relevance to
            # WHO IS OUT first, then talent, then the human cost. The hole's
            # line tells us the missing role -- top-six holes (lines 0/1)
            # want scoring roles, bottom-six holes (lines 2/3) want checking
            # roles, D-pair holes want stay-at-home types. A 4th-line hole
            # goes to a checker, NOT the first-line sniper: graded role fit,
            # never best-overall. Stars CAN double-shift (realistic) but
            # fatigue/condition genuinely bite -- they're human -- and the
            # load spreads instead of stacking one star on every hole. And
            # sometimes the coach just skates short: a poor-fit, tired body
            # is worse than redistributed minutes, so the hole stays empty.
            _F_TOP_FIT = {      # scoring-line hole
                "Sniper": 1.00, "Playmaker": 0.90, "Power Forward": 0.85,
                "Two-Way Forward": 0.60, "Grinder": 0.25, "Enforcer": 0.15,
                "Offensive Defenseman": 0.30, "Two-Way Defenseman": 0.30,
                "Defensive Defenseman": 0.20,
            }
            _F_BOT_FIT = {      # checking-line hole
                "Grinder": 1.00, "Two-Way Forward": 0.85,
                "Power Forward": 0.60, "Enforcer": 0.50,
                "Sniper": 0.25, "Playmaker": 0.25,
                "Defensive Defenseman": 0.30, "Two-Way Defenseman": 0.30,
                "Offensive Defenseman": 0.20,
            }
            _D_PAIR_FIT = {     # D-pair hole
                "Defensive Defenseman": 1.00, "Two-Way Defenseman": 0.70,
                "Offensive Defenseman": 0.40, "Grinder": 0.30,
                "Two-Way Forward": 0.30, "Power Forward": 0.25,
                "Sniper": 0.15, "Playmaker": 0.15, "Enforcer": 0.20,
            }
            _role_name = {}
            _cond = {}
            for _p in assigned:
                try:
                    _r = _p.get_role()
                    _role_name[id(_p)] = (getattr(_r, "value", "")
                                          or str(_r))
                except Exception:
                    _role_name[id(_p)] = ""
                try:
                    _cond[id(_p)] = max(0.0, min(100.0, float(
                        getattr(_p, "condition", 100.0) or 100.0)))
                except Exception:
                    _cond[id(_p)] = 100.0

            def _hole_fit(_p, _kind, _unit_idx):
                _table = (_F_TOP_FIT if (_kind == "F" and _unit_idx < 2)
                          else _F_BOT_FIT if _kind == "F"
                          else _D_PAIR_FIT)
                return _table.get(_role_name.get(id(_p), ""), 0.35)

            def _best_for(_unit, _kind, _unit_idx):
                _ids = {id(_q) for _q in (_unit or []) if _q is not None}
                _cands = [p for p in assigned if id(p) not in _ids]
                if not _cands:
                    return None

                def _score(_p):
                    _pid = id(_p)
                    _talent = _ovr.get(_pid, 0.0) / 100.0
                    _fit = _hole_fit(_p, _kind, _unit_idx)
                    # Human cost: a gassed star double-shifts badly.
                    _cm = 0.55 + 0.45 * (_cond.get(_pid, 100.0) / 100.0)
                    # Spread the emergency load: each extra unit already
                    # skated discounts the candidate steeply.
                    _load = 1.0 / (1.0 + 0.75 * max(
                        0, use_count.get(_pid, 0) - 1))
                    return _talent * (0.45 + 0.55 * _fit) * _cm * _load

                _cands.sort(key=lambda p: -_score(p))
                _fill = _cands[0]
                # Skate short: the best available body is a poor role fit
                # AND tired -- the coach takes the short bench over a bad
                # double-shift, and the minutes redistribute.
                if (_hole_fit(_fill, _kind, _unit_idx) < 0.50
                        and _cond.get(id(_fill), 100.0) < 75.0):
                    return None
                use_count[id(_fill)] = use_count.get(id(_fill), 0) + 1
                return _fill

            for _li, _line in enumerate(fw_lines):
                for _ji in range(len(_line or [])):
                    if _line[_ji] is None:
                        _fill = _best_for(_line, "F", _li)
                        if _fill is not None:
                            _line[_ji] = _fill
            for _pi, _pair in enumerate(def_pairs):
                for _ji in range(len(_pair or [])):
                    if _pair[_ji] is None:
                        _fill = _best_for(_pair, "D", _pi)
                        if _fill is not None:
                            _pair[_ji] = _fill
        except Exception:
            pass

    _repair_es_slots()

    # Build the complete lineup
    lines = {
        'Forwards': fw_lines,
        'Defense': def_pairs,
        'Goalies': goalies[:2] if len(goalies) >= 2 else goalies + [None] * (2 - len(goalies)),
        'PP1': {'Forwards': pp1_forwards, 'Defense': pp1_defense},
        'PP2': {'Forwards': pp2_forwards, 'Defense': pp2_defense},
        'PK1': {'Forwards': pk1_forwards, 'Defense': pk1_defense},
        'PK2': {'Forwards': pk2_forwards, 'Defense': pk2_defense},
        'Strategies': {
            'EvenStrength': 'Balanced',
            'PowerPlay': 'Offensive',
            'PenaltyKill': 'Defensive',
            'LeadingBy2+': 'Defensive',
            'TrailingBy2+': 'Very Offensive',
            'ForeCheckIntensity': 50,
            'DefensiveStructure': 'Standard',
            'Aggression': 50
        }
    }
    return flatten_lineup(lines)


def user_controlled_lines(team):
    """Item 5 (line_control wiring): the lineup a sim path must dress for `team`.

    The lineup pen lives on team.line_control ('coach' | 'gm'; see
    reputation_system.set_line_control):
    - 'gm': the GM holds the pen, so the team's USER-SET lines
      (team.lineup, as arranged in the lineup editor) are what the sim
      must dress. Returns the stored dict when one exists; None when the
      team has no user-set lines stored -- the caller then falls back to
      the coach's builder exactly as it does today.
    - anything else (including a missing flag): None. The caller keeps
      today's behavior byte-for-byte.
    Pure: never raises, never mutates.
    """
    try:
        if getattr(team, "line_control", "coach") != "gm":
            return None
        lineup = getattr(team, "lineup", None)
        if isinstance(lineup, dict) and lineup:
            return lineup
    except Exception:
        pass
    return None


def flatten_lineup(lineup):
    """Add flat F1_LW..F4_RW / D1_L..D3_R keys the sim reads, from nested lines.

    Editors and best_lines() write nested {'Forwards': [[LW,C,RW]x4],
    'Defense': [[L,R]xN], 'Goalies': [...]}. GameSim._get_on_ice reads flat
    keys, so without this the sim silently ignores user lines and dresses
    best-available-by-overall instead. Idempotent: safe to call repeatedly.
    """
    if not isinstance(lineup, dict):
        return lineup
    # Clear stale flat keys first: if a slot was emptied or replaced, an old
    # assignment must not linger and dress the wrong player.
    import re as _re
    _flat_pat = _re.compile(r'^[FD]\d+_[LRCW]+$|^G\d+$')
    for key in list(lineup.keys()):
        if _flat_pat.match(key):
            del lineup[key]
    forwards = lineup.get('Forwards') or []
    for i, line in enumerate(forwards[:4]):
        if not line:
            continue
        for j, key in enumerate(('LW', 'C', 'RW')):
            try:
                player = line[j] if isinstance(line, (list, tuple)) else None
            except (IndexError, TypeError):
                player = None
            if player:
                lineup[f"F{i + 1}_{key}"] = player
    defense = lineup.get('Defense') or []
    for i, pair in enumerate(defense[:4]):
        if not pair:
            continue
        try:
            ld = pair[0] if isinstance(pair, (list, tuple)) else None
            rd = pair[1] if isinstance(pair, (list, tuple)) and len(pair) > 1 else None
        except (IndexError, TypeError):
            ld = rd = None
        if ld:
            lineup[f"D{i + 1}_L"] = ld
        if rd:
            lineup[f"D{i + 1}_R"] = rd
    goalies = lineup.get('Goalies') or []
    for i, goalie in enumerate(goalies[:2]):
        if goalie:
            lineup[f"G{i + 1}"] = goalie
    return lineup


def resolve_game_lineup(team, context=None):
    """The one shared lineup-resolution decision (one decision, two
    fidelities). Previously a closure inside AdvancedGameSim.__init__;
    GameSim resolves the same way, so both engines dress from the same
    decision instead of two copies.

    ``context`` (optional dict): {"playoffs": bool} -- lets the D24
    play-hurt pass know when the coach may demand a star play hurt for
    cause. Absent == regular-season game.

    Precedence:
      1. suspension scrub (mutates the stored team.lineup in place);
      2. GM lines: user_controlled_lines() (line_control == 'gm' with a
         stored user-set lineup -- the GM's set lines are the law);
      3. the team's stored lineup (e.g. user team arranged in the editor);
      4. best_lines(team) coach fallback -- the fix path for AI teams that
         never get a lineup built in the season/batch-sim path;
      5. defensive backfill: a stored lineup missing any of
         ['Forwards', 'Defense', 'Goalies'] gets just those keys from
         best_lines() (notably NOT PP/PK/flat keys -- same as before).
    Pure contract: best_lines()/user_controlled_lines() are module-level
    helpers already; the suspension scrub is lazy-imported, preserving the
    no-module-level-cross-import convention.
    """
    # Suspended players can't dress: scrub them from a stored
    # lineup before the sim reads it (fresh builds already filter
    # via best_lines' _healthy).
    try:
        from narrative_incidents import _scrub_suspended_from_lineup
        _scrub_suspended_from_lineup(team)
    except Exception:
        pass
    # Item 5: the GM holds the pen -> his set lines are the law.
    # user_controlled_lines() returns None unless the flag is 'gm'
    # with stored user lines, so every other case keeps today's
    # behavior byte-for-byte.
    _gm_lines = user_controlled_lines(team)
    lineup = (_gm_lines if _gm_lines is not None
              else getattr(team, 'lineup', None))
    if not lineup or not isinstance(lineup, dict):
        lineup = best_lines(team)
        # Coach-built fallback gets the hot-hand audition too (GM law
        # doesn't apply — these are the coach's lines).
        try:
            from line_chemistry import hot_hand_auditions as _lcha2
            lineup, _ = _lcha2(team, lineup)
        except Exception:
            pass
        return apply_play_hurt_management(team, lineup, context)
    # Defensive: fill missing keys with best_lines
    keys = ['Forwards', 'Defense', 'Goalies']
    missing = [k for k in keys if k not in lineup]
    if missing:
        base = best_lines(team)
        for k in missing:
            lineup[k] = base[k]
    # Hot-hand audition (2026-09-30, Muck): form is first-class in coach
    # selection. Heaters earn a one-line look (bounded, talent-guarded,
    # never changes who dresses); sustained auditions earn the spot,
    # faded ones go back down — the experiment ledger tracks it all.
    # Coach paths only: the GM's set lines are the law.
    if _gm_lines is None:
        try:
            from line_chemistry import hot_hand_auditions as _lcha
            lineup, _ = _lcha(team, lineup)
        except Exception:
            pass
    # D24 (Wave A): nobody is forced back gassed at full condition.
    return apply_play_hurt_management(team, lineup, context)


# ---------------------------------------------------------------------------
# D24 -- play-hurt / load management (Wave A, 2026-10-01, Muck)
# ---------------------------------------------------------------------------
# Nobody is forced into the lineup gassed or half-recovered at full role.
# This pass runs inside resolve_game_lineup (the one shared decision), so
# both engines dress from it. For each dressed skater who is gassed
# (condition < 50), worn-and-recently-returned, or inside the re-injury
# window:
#   * a healthy scratch is available AND it is not the playoffs and not an
#     injury crisis -> load management: he sits, the best healthy
#     replacement draws in (dynamics-logged);
#   * otherwise (playoffs, crisis, no depth) -> he dresses PLAYING HURT:
#     tagged, deployment sheds his minutes (D17), re-injury risk rises.
#     A playoff demand is the coach's call for cause -- logged with
#     morale/fallout weight.
# Playing hurt is never at maximum condition: the wear shows in his
# minutes (deployment), and the tag clears every game (per-game state).
# Goalies are excluded -- the starter rotation owns their load.

def _play_hurt_risk(player):
    """'high' / 'medium' / None for the D24 pass. Never raises."""
    try:
        from condition_system import get_condition as _gc
        cond = _gc(player)
    except Exception:
        cond = 100.0
    try:
        gsr = getattr(player, "games_since_return", 999)
        gsr = int(gsr) if gsr is not None else 999
    except Exception:
        gsr = 999
    try:
        from injury_data import REINJURY_WINDOW_GAMES as _rw
    except Exception:
        _rw = 10
    if cond < 50.0 or gsr < 5:
        return "high"
    if cond < 65.0 or gsr < _rw:
        return "medium"
    return None


def apply_play_hurt_management(team, lineup, context=None):
    """D24 lineup pass. Never raises; returns the lineup (possibly with
    scratches swapped)."""
    try:
        import condition_system as _cs
    except Exception:
        return lineup
    try:
        ctx = context or {}
        playoffs = bool(ctx.get("playoffs"))
        if not isinstance(lineup, dict):
            return lineup
        roster = getattr(team, "roster", None) or []
        # Per-game tag: clear stale flags first.
        for _p in roster:
            try:
                if getattr(_p, "playing_hurt", False):
                    _p.playing_hurt = False
            except Exception:
                continue

        def _dressed_ids():
            ids = set()
            for _ln in (lineup.get("Forwards") or []):
                for _p in (_ln or []):
                    if _p is not None:
                        try:
                            ids.add(_p.id)
                        except Exception:
                            pass
            for _pr in (lineup.get("Defense") or []):
                for _p in (_pr or []):
                    if _p is not None:
                        try:
                            ids.add(_p.id)
                        except Exception:
                            pass
            return ids

        def _is_dman(_p):
            try:
                return _p.primary_position.name in (
                    "LEFT_DEFENSE", "RIGHT_DEFENSE", "DEFENSE")
            except Exception:
                return False

        def _healthy_scratch(side):
            """Best healthy, fresh scratch on this side (F/D)."""
            dressed = _dressed_ids()
            cands = []
            for _p in roster:
                try:
                    if _p.id in dressed:
                        continue
                    if getattr(_p, "is_injured", False):
                        continue
                    if getattr(_p, "suspension_games_remaining", 0) or 0:
                        continue
                    if _p.primary_position.name == "GOALIE":
                        continue
                    if _is_dman(_p) != (side == "D"):
                        continue
                    if _cs.get_condition(_p) < 65.0:
                        continue
                    cands.append(_p)
                except Exception:
                    continue
            if not cands:
                return None
            cands.sort(key=lambda _p: _cs.get_condition(_p),
                       reverse=True)
            return cands[0]

        def _swap_in(line_key, slot_idx, pos_idx, new_p):
            """Swap a skater in the nested lineup, then re-flatten."""
            try:
                unit = lineup.get(line_key)
                if not unit or slot_idx >= len(unit):
                    return False
                slot = unit[slot_idx]
                if not isinstance(slot, list) or pos_idx >= len(slot):
                    return False
                slot[pos_idx] = new_p
                flatten_lineup(lineup)  # refresh F1_LW.. keys
                return True
            except Exception:
                return False

        def _log(text, morale_delta=0, tone="neutral"):
            try:
                from reputation_system import record_team_event as _rte
                _rte(team, "coach_demand", text,
                     morale_delta=morale_delta, tone=tone)
            except Exception:
                pass

        tname = getattr(team, "team_name", "?")
        # Forwards.
        for _li, _line in enumerate(lineup.get("Forwards") or []):
            if not isinstance(_line, list):
                continue
            for _pi, _p in enumerate(list(_line)):
                if _p is None:
                    continue
                try:
                    risk = _play_hurt_risk(_p)
                except Exception:
                    risk = None
                if risk is None:
                    continue
                _pname = getattr(_p, "full_name", "A skater")
                if risk == "high" and not playoffs:
                    _rep = _healthy_scratch("F")
                    if _rep is not None:
                        if _swap_in("Forwards", _li, _pi, _rep):
                            _rname = getattr(_rep, "full_name", "?")
                            _log(f"Load management: {_pname} sits "
                                 f"(gassed/recovering) -- {_rname} draws "
                                 f"in for {tname}.",
                                 morale_delta=0, tone="neutral")
                            try:
                                _p.happiness = max(
                                    1, (getattr(_p, "happiness", 70)
                                        or 70) - 3)
                            except Exception:
                                pass
                            continue
                # Plays hurt: tag it; deployment sheds his minutes (D17),
                # re-injury risk rises (injury_data).
                try:
                    _p.playing_hurt = True
                except Exception:
                    pass
                if playoffs and risk == "high":
                    _log(f"Coach's call: {_pname} plays hurt for "
                         f"{tname} in the playoffs -- the room notices.",
                         morale_delta=2, tone="up")
                    try:
                        _p.happiness = max(
                            1, (getattr(_p, "happiness", 70) or 70) - 4)
                    except Exception:
                        pass
        # Defense pairs.
        for _pi2, _pair in enumerate(lineup.get("Defense") or []):
            if not isinstance(_pair, list):
                continue
            for _pj, _p in enumerate(list(_pair)):
                if _p is None:
                    continue
                try:
                    risk = _play_hurt_risk(_p)
                except Exception:
                    risk = None
                if risk is None:
                    continue
                _pname = getattr(_p, "full_name", "A skater")
                if risk == "high" and not playoffs:
                    _rep = _healthy_scratch("D")
                    if _rep is not None:
                        if _swap_in("Defense", _pi2, _pj, _rep):
                            _rname = getattr(_rep, "full_name", "?")
                            _log(f"Load management: {_pname} sits "
                                 f"(gassed/recovering) -- {_rname} draws "
                                 f"in for {tname}.",
                                 morale_delta=0, tone="neutral")
                            try:
                                _p.happiness = max(
                                    1, (getattr(_p, "happiness", 70)
                                        or 70) - 3)
                            except Exception:
                                pass
                            continue
                try:
                    _p.playing_hurt = True
                except Exception:
                    pass
                if playoffs and risk == "high":
                    _log(f"Coach's call: {_pname} plays hurt for "
                         f"{tname} in the playoffs -- the room notices.",
                         morale_delta=2, tone="up")
                    try:
                        _p.happiness = max(
                            1, (getattr(_p, "happiness", 70) or 70) - 4)
                    except Exception:
                        pass
        return lineup
    except Exception:
        return lineup

# ---------------------------------------------------------------------------
# D11 (2026-09-30, per Muck: CONSOLIDATE): AdvGS speed-optimized
# approximation of the ONE shared shot-fate decision
# (mesh_system.shot_fate). Same inputs, same formula -- the ONLY
# differences are computational:
#   1. The defending unit's best blocker is resolved ONCE PER UNIT (not
#      per shot) and cached as (blocker, unit_battle, unit_tendency,
#      unit_composite). The D corps does not change within a QS shift,
#      so this is exact while the unit is unchanged; the cache key is
#      the unit's composition.
#   2. Per shot, only the shooter's two battle attributes are read; the
#      defender side comes from the cache. No per-attribute lookups over
#      the D corps per shot.
# What is NOT approximated: the formula itself. This computes literally
# mesh_system.shot_block_prob's math (0.08 + battle*0.004, lane mult,
# situation mults, 0.01-0.50 rails) and mesh_system.shot_miss_prob's
# math. Proof: qa_d11_parity.py feeds identical contexts to both paths
# and reports the agreement rate.
# Engine-fidelity INPUT differences (documented, not formula
# differences -- AdvGS genuinely lacks this state):
#   - location: derived from the shooter's rink coordinates via the
#     shared _SHOT_SPOTS geometry (nearest spot in the attacking
#     orientation). GameSim passes its live ShotLocation.
#   - distance: coordinate distance to the goal mouth. GameSim passes
#     its location-based distance.
#   - situation: AdvGS has no defensive-system / DZ-tactic / pressure /
#     installed-tactics state (the deployment layer is GameSim-only;
#     queued parity work) -> neutral 1.0 for sys/dz/pressure/tactics.
#     tendency + composite come from the cached best blocker (the
#     composite WITHOUT energy, exactly as GameSim's block path calls
#     it); fatigue is the live shift-fatigue curve value.
# ---------------------------------------------------------------------------
class ApproxFate(NamedTuple):
    """Result of approx_shot_fate. fate/blocker mirror mesh ShotFate;
    p_block/p_miss expose the probabilities for the equivalence proof."""
    fate: str
    blocker: object
    p_block: float
    p_miss: float


def _qs_shot_spots():
    """GameSim's _SHOT_SPOTS geometry (single source of truth, lazy to
    avoid import weight at module load). Never raises."""
    try:
        from simulation import GameSim as _GS
        return dict(_GS._SHOT_SPOTS)
    except Exception:
        return {}


def qs_shot_location(shooter_x, shooter_y, attacking_plus_x=True):
    """Nearest _SHOT_SPOTS location key to a rink coordinate, in the
    attacking orientation. AdvGS's documented proxy for GameSim's live
    ShotLocation (AdvGS does not track it). Never raises; None when the
    geometry is unavailable."""
    try:
        _spots = _qs_shot_spots()
        if not _spots:
            return None
        _x = float(shooter_x)
        if not attacking_plus_x:
            _x = 200.0 - _x
        _y = float(shooter_y)
        _best, _best_d = None, None
        for _k, (_sx, _sy) in _spots.items():
            _d = (_x - _sx) ** 2 + (_y - _sy) ** 2
            if _best_d is None or _d < _best_d:
                _best, _best_d = _k, _d
        return _best
    except Exception:
        return None


def qs_shot_distance(shooter_x, shooter_y, attacking_plus_x=True):
    """Coordinate distance (feet) from the shooter to the goal mouth.
    AdvGS's documented proxy for GameSim's location-based distance.
    Never raises; None when coordinates are unusable."""
    try:
        _gx = 189.0 if attacking_plus_x else 11.0
        return float(math.hypot(float(shooter_x) - _gx,
                                float(shooter_y) - 42.5))
    except Exception:
        return None


def approx_block_prob(shooter, unit, location=None, situation=None,
                      _rng=None):
    """The block arm of approx_shot_fate: the SAME math as
    mesh_system.shot_block_prob (0.08 + battle*0.004, lane mult,
    situation mults, 0.01-0.50 rails), with the defender's battle half
    arriving pre-resolved in `unit` = (blocker, unit_battle,
    unit_tendency, unit_composite). Returns (blocked, blocker, p_block).
    An explicitly passed situation tendency/composite wins over the
    unit's cached values. Never raises."""
    try:
        from mesh_system import (_lane_mult as _lm,
                                 SHOT_FATE_SITUATION_KEYS as _KEYS)
        _rand = _rng.random if _rng is not None else random.random
        _blocker, _ubattle, _utend, _ucomp = unit
        if _blocker is None or _ubattle is None:
            return (False, None, 0.0)
        _sht = (float(getattr(shooter, "offensive_awareness", 10)) * 0.50
                + float(getattr(shooter, "composure", 10)) * 0.50)
        _battle = _ubattle - _sht
        _p = 0.08 + _battle * 0.004
        _p *= _lm(location)
        _sit = dict(situation or {})
        _sit.setdefault("tendency", _utend)
        _sit.setdefault("composite", _ucomp)
        for _k in _KEYS:
            try:
                _p *= float(_sit.get(_k, 1.0))
            except Exception:
                pass
        _p = max(0.01, min(0.50, _p))
        return (_rand() < _p, _blocker, _p)
    except Exception:
        return (False, None, 0.0)


def approx_shot_fate(shooter, defenders, grade="B", location=None,
                     distance=None, situation=None, weights=None,
                     unit=None, _rng=None) -> ApproxFate:
    """Speed-optimized approximation of mesh_system.shot_fate: the SAME
    decision, with the defending unit pre-resolved.

    unit: optional (blocker, unit_battle, unit_tendency, unit_composite)
    tuple from the per-unit cache -- skips the per-shot blocker
    resolution and per-attribute lookups. When None, the blocker is
    resolved exactly (same as the shared path); the equivalence proof
    uses this mode against mesh_system.shot_fate.
    situation: same keys as the shared decision; sys/dz/pressure/
    tactics default to 1.0. tendency/composite default to 1.0 unless
    supplied by `unit` or `situation`.
    Never raises.
    """
    try:
        from mesh_system import (resolve_blocker as _rb,
                                 defensive_positioning as _dp,
                                 shot_miss_prob as _smp)
        _rand = _rng.random if _rng is not None else random.random
        _blocker, _ubattle, _utend, _ucomp = None, None, 1.0, 1.0
        if unit is not None:
            _blocker, _ubattle, _utend, _ucomp = unit
        else:
            _blocker = _rb(defenders, weights) if defenders else None
        _unit2 = (_blocker, _ubattle, _utend, _ucomp)
        if _blocker is not None and _ubattle is None:
            # Exact-resolution mode: the defender's battle HALF from the
            # resolved blocker (approx_block_prob subtracts the
            # shooter's live half itself) -- same math as the shared
            # path's full battle.
            _unit2 = (_blocker,
                      _dp(_blocker) * 0.50
                      + float(getattr(_blocker, "shot_blocking", 10)) * 0.50,
                      _utend, _ucomp)
        _blocked, _blocker2, _p_block = approx_block_prob(
            shooter, _unit2, location, situation, _rng=_rng)
        if _blocked:
            return ApproxFate("blocked", _blocker2, _p_block, 0.0)
        _p_miss = _smp(shooter, grade, distance)
        if _rand() < _p_miss:
            return ApproxFate("missed", None, _p_block, _p_miss)
        return ApproxFate("on_net", None, _p_block, _p_miss)
    except Exception:
        return ApproxFate("on_net", None, 0.0, 0.0)


class AdvancedGameSim:
    """Simulates a hockey game and produces a structured event log for visualization."""

    def __init__(self, home_team, away_team, atmosphere=None, league=None, is_playoff=False):
        self.home_team = home_team
        self.away_team = away_team
        # League passthrough (ot_drama): enables rivalry heat, which reads
        # league.rivalries and is otherwise always 0 in headless use.
        # Default None = today's behavior exactly.
        self.league = league
        # L1 (Muck 2026-10-01): playoff context for lineup parity with GameSim.
        # GameSim passes {"playoffs": bool(is_playoff)} to resolve_game_lineup;
        # quick_sim passed nothing, making D24 playoff load-management dead
        # on the quick-sim path. One decision, two fidelities.
        self.is_playoff = bool(is_playoff)
        # §5.1 (2026-09-30, Muck): converge on ONE rivalry mechanism. The
        # shared circumstance_shift read resolves sim.rivalries — expose it
        # here from the league passthrough (the same source the mesh path
        # reads), so both engines feel rivalry in the physical/discipline
        # channel identically. The mesh game_ctx["rivalry_heat"] path feeds
        # chance VOLUME (a different, pre-existing effect) — not double-
        # counted, left exactly as specced per §5.3.
        try:
            self.rivalries = list(getattr(league, "rivalries", None) or [])
        except Exception:
            self.rivalries = []
        # §5.2 (2026-09-30, Muck): the shared bounded in-game heat
        # accumulator. Quick-sim has no fights/brawls, so heat builds from
        # penalties (a chippy game boils the same way) — same 0-40 scale
        # and semantics as GameSim via scenario_composites.add_live_heat.
        try:
            from scenario_composites import LiveHeat as _LHq
            self._heat_acc = _LHq()
        except Exception:
            self._heat_acc = None
        self._live_heat = 0.0  # legacy read path (add_live_heat fallback)
        # Part B: bounded assist-pairs ledger (passer_id, scorer_id,
        # team_name), same shape as GameSim's, for line-combination
        # analytics.
        self.assist_pairs = deque(maxlen=4000)
        # Shot-volume realism (2026-09-30, Muck: one puck, shared with
        # linemates -- NOT a flat cap). Parity with GameSim's
        # _recent_shooters (simulation.py): the last 8 shooters per team;
        # a player who just shot sees his choice weight cut (x0.35) --
        # "you just shot; the puck moves on." One decision, two
        # fidelities. AdvancedGameSim is constructed per game, so the
        # deques reset naturally every game.
        self._recent_shooters = {
            home_team.team_name: deque(maxlen=8),
            away_team.team_name: deque(maxlen=8),
        }
        # FM team-talk boost: team_name -> multiplier (default 1.0)
        self.team_boost = {home_team.team_name: 1.0, away_team.team_name: 1.0}

        # Crowd (arena_atmosphere): the building is a two-sided factor. A
        # jacked crowd lifts the home side; a nervous/toxic one drags it; a
        # loud hostile barn rattles young visitors while veterans shrug.
        # Feeds the existing finishing channels -- own keys, never shares the
        # team-talk/dressing-room keys, so nothing can overwrite it.
        self._crowd_energy = 50.0
        self._crowd_mood_home = 30.0
        self._crowd_home_mult = 1.0
        self._crowd_away_mult = 1.0
        self._init_crowd(atmosphere)
        # Hostile homecomings (Wave C D39): same shared read as GameSim.
        self._apply_homecoming_pregame()

        # Dressing-room talks (module 03): each side's pre-game words move
        # finishing a touch. Own channel -- never shares the legacy
        # team_boost key, so the career team-talk system can't overwrite it.
        self.dressing_boost = {
            home_team.team_name: 1.0, away_team.team_name: 1.0}
        self._apply_dressing_room_pregame()

        # Situations factor: pre-game room/bench/hunger edge per side,
        # computed once here (the per-shot loop only reads the multiplier).
        self._init_situations()

        # Goalie personality state (divergence #10): per-goalie, per-game
        # state (bounce-back, tilt, off-night) -- the same decision GameSim
        # makes with its goalie_personality_state dict. Seeded per goalie
        # below; charged on every goal allowed.
        self.goalie_personality_state = {}

        # Installed NHL systems (tactics.py): per-game matchup edge per
        # side, computed once here -- the per-shot loop only reads.
        self._init_systems_edge()

        # Parity engine: cross-game form + the corrective layer (coach
        # adjustments, new-coach bounce, veteran pride, target-on-back,
        # trap games). Same shared decision GameSim calls; this engine
        # applies it on shot probability.
        self._init_parity_edge()

        # Initialize performance cache
        from performance_optimizations import get_global_cache
        self.cache = get_global_cache()
        
        # Initialize coordinate-based simulation engine
        from coordinate_simulation import CoordinateSimEngine
        self.coordinate_engine = CoordinateSimEngine()

        # Defensive: always ensure lineup dict has required keys.
        # Shared decision with GameSim (resolve_game_lineup): one decision,
        # two fidelities -- the closure body now lives at module level.
        # L1: pass playoff context (GameSim passes {"playoffs": bool(is_playoff)}).
        def ensure_lineup(team):
            return resolve_game_lineup(team, {"playoffs": self.is_playoff})

        self.lineups = {
            home_team.team_name: ensure_lineup(home_team),
            away_team.team_name: ensure_lineup(away_team)
        }
        # WS1 parity: the canonical per-game energy pool starts at 100 for
        # both clubs -- the shared reset_game_fatigue GameSim calls on its
        # first tick (simulation._update_fatigue). Without it, a previous
        # watched game's drained pool would leak into a quick-simmed game.
        # Never raises.
        try:
            from condition_system import reset_game_fatigue as _rgf
            for _t in (home_team, away_team):
                for _p in getattr(_t, "roster", None) or []:
                    _rgf(_p)
        except Exception:
            pass
        self.score = {home_team.team_name: 0, away_team.team_name: 0}
        self.events = []
        # Analytics integration (2026-10-01): lightweight per-shot log
        # for the Analytics Hub -- grade, xg (from grade), outcome, and
        # the scenario/composite chance context. quick_sim never had
        # shot-level analytics; this is the fast approximation of
        # GameSim._analytics_record_shot (same record shape, minimal
        # fields). Additive; never affects engine decisions.
        self._analytics_shots = []
        self.stats = {
            home_team.team_name: {p.id: {'goals': 0, 'assists': 0, 'shots': 0, 'toi': 0, 'fatigue': 0} for p in home_team.roster},
            away_team.team_name: {p.id: {'goals': 0, 'assists': 0, 'shots': 0, 'toi': 0, 'fatigue': 0} for p in away_team.roster}
        }
        # Ensure stats dict includes all stat keys for each player
        for team in [home_team, away_team]:
            for p in team.roster:
                self.stats[team.team_name][p.id] = {
                    'goals': 0, 'assists': 0, 'shots': 0, 'saves': 0, 'penalties': 0, 'toi': 0, 'fatigue': 0
                }
        self.puck_pos = 'neutral'
        self.time = 0
        self.period = 1
        self.on_ice = {
            home_team.team_name: {'Forwards': [], 'Defense': [], 'Goalie': None},
            away_team.team_name: {'Forwards': [], 'Defense': [], 'Goalie': None}
        }
        self.pp_team = None
        self.pk_team = None
        self.pp_end_time = None  # When the current power play expires (penalty clock)
        # Goalie pulls / 6-on-5 (parity with GameSim): team names with the
        # net empty. Checked once per shift in period 3; goalies return on
        # any goal and at period ends.
        self.goalie_pulled = set()
        # Structured drama (workstream B, 2026-09-30, additive): measurement
        # reads sim.drama_events -- broadcast keeps its text log unchanged.
        # QS has no delayed-penalty pulls (all pulls are strategic).
        self._pull_clock = {}  # team name -> time remaining at the pull
        try:
            from drama_events import init_drama_events as _ide
            _ide(self)
        except Exception:
            self.drama_events = []
        # EHM shift-fatigue: continuous seconds the current on-ice unit has
        # been out. Most shifts rotate; stuck units accumulate and degrade.
        self._shift_age = {home_team.team_name: 0.0, away_team.team_name: 0.0}
        # D11: per-unit cached block resolution for approx_shot_fate --
        # keyed on the D corps' composition (blocker, unit_battle,
        # unit_tendency, unit_composite). Cleared per game in run().
        self._block_unit_cache = {}
        # Last-change edge: home responds to the away line declaration.
        # Recomputed per shift; 1.0 when the home coach just rolls.
        self._matchup_edge = {home_team.team_name: 1.0, away_team.team_name: 1.0}
        # Head coaches for personality-driven decisions (goalie-pull timing).
        # goalie_pull.coach_for reads these; None -> balanced default.
        self._home_coach = self._find_head_coach(home_team)
        self._away_coach = self._find_head_coach(away_team)
        self.puck_x = 100  # X position of puck on ice (center ice)
        self.puck_y = 42.5  # Y position of puck on ice (center)
        self.state_history = []  # List to store state after each shift/event
        self.event_log = []  # Structured event log for visualization
        
        # Initialize player positions using coordinate engine
        home_players = [p for p in home_team.roster]
        away_players = [p for p in away_team.roster] 
        self.coordinate_engine.initialize_player_positions(home_players, away_players)

    def set_team_talk_boost(self, team_name: str, multiplier: float):
        """FM-style: apply a team-talk/morale multiplier to a team's scoring."""
        self.team_boost[team_name] = max(0.9, min(1.1, multiplier))

    # -- D1: coach-instruction channel (uniform with GameSim) ------------
    # AdvancedGameSim never classifies hits, so an instruction is
    # currently INERT on the quick path -- the channel exists so the
    # game-day bundle can set one uniformly and any future consumer
    # reads the same _coach_instructions shape. Never raises.
    def set_coach_instruction(self, team_name, instruction):
        """Set a coach instruction for a team (e.g. "play_harder").
        Pass None to clear. Explicit sets (game-day bundle) are tracked
        so the AI refresh never overwrites a human call -- same provenance
        rule as GameSim."""
        try:
            if not hasattr(self, "_coach_instructions"):
                self._coach_instructions = {}
            if not hasattr(self, "_coach_instruction_source"):
                self._coach_instruction_source = {}
            if instruction:
                self._coach_instructions[team_name] = instruction
                self._coach_instruction_source[team_name] = "explicit"
            else:
                self._coach_instructions.pop(team_name, None)
                self._coach_instruction_source.pop(team_name, None)
        except Exception:
            pass

    def get_coach_instruction(self, team):
        try:
            return self._coach_instructions.get(
                getattr(team, "team_name", None))
        except Exception:
            return None

    # -- D1 design build: live instruction refresh (fast fidelity) --------
    # The SAME shared decision as the watched path
    # (mesh_system.ai_coach_instruction_for) with this engine's fast
    # state: score dict, period, cumulative time, head coaches, rivalry
    # heat. No feed announcements on the quick path. Explicit user
    # instructions are never overwritten. Never raises.
    def _refresh_coach_instructions(self, flags_by_team=None):
        try:
            from mesh_system import ai_coach_instruction_for as _aii
            if not hasattr(self, "_coach_instructions"):
                self._coach_instructions = {}
            if not hasattr(self, "_coach_instruction_source"):
                self._coach_instruction_source = {}
            _fb = flags_by_team or {}
            _per = int(getattr(self, "period", 1) or 1)
            try:
                _t = max(0.0, 1200.0 * _per - float(getattr(self, "time", 0)
                                                    or 0))
            except Exception:
                _t = 1200.0
            for _team, _coach in (
                    (self.home_team, getattr(self, "_home_coach", None)),
                    (self.away_team, getattr(self, "_away_coach", None))):
                try:
                    _tn = getattr(_team, "team_name", "") or ""
                    if not _tn:
                        continue
                    if (self._coach_instruction_source.get(_tn)
                            == "explicit"):
                        continue
                    _other = (self.away_team if _team is self.home_team
                              else self.home_team)
                    _diff = (int(self.score.get(_tn, 0))
                             - int(self.score.get(
                                 getattr(_other, "team_name", ""), 0)))
                    _pp = getattr(self, "pp_team", None)
                    _pk = getattr(self, "pk_team", None)
                    _heat = 0.0
                    try:
                        import reputation_system as _rsq
                        _lg = getattr(self, "league", None)
                        _rivs = (getattr(_lg, "rivalries", None)
                                 if _lg else None)
                        if _rivs:
                            _rh = _rsq.get_rivalry_heat(_rivs, _team, _other)
                            _heat = float((_rh or {}).get("heat", 0) or 0)
                    except Exception:
                        pass
                    _want = _aii(_diff, _per, _t, _coach,
                                 flags=_fb.get(_tn), rivalry_heat=_heat,
                                 on_pp=_pp == _tn, on_pk=_pk == _tn)
                    _have = self._coach_instructions.get(_tn)
                    if _want == _have:
                        continue
                    if _want:
                        self._coach_instructions[_tn] = _want
                        self._coach_instruction_source[_tn] = "ai"
                    else:
                        self._coach_instructions.pop(_tn, None)
                        self._coach_instruction_source.pop(_tn, None)
                except Exception:
                    continue
        except Exception:
            pass

    def _instruction_effect(self, team_name, channel, default=1.0):
        """D1: this team's instruction effect channel (fast path).

        Multipliers are efficacy-scaled on the delta (bounded). Never
        raises.
        """
        try:
            from mesh_system import (coach_instruction_effects as _cie,
                                     coach_instruction_efficacy as _ceff)
            _instrs = getattr(self, "_coach_instructions", {}) or {}
            _fx = _cie(_instrs.get(team_name, ""))
            _v = float(_fx.get(channel, default))
            if _v == default:
                return default
            _coach = (getattr(self, "_home_coach", None)
                      if team_name == getattr(self.home_team, "team_name",
                                             "")
                      else getattr(self, "_away_coach", None))
            _eff = _ceff(_coach)
            return 1.0 + (_v - 1.0) * _eff
        except Exception:
            return default

    # -- Crowd (arena_atmosphere) -------------------------------------------
    def _init_crowd(self, atmosphere):
        """Seed crowd state from a pregame_crowd() dict (or a quiet default)."""
        try:
            from arena_atmosphere import crowd_effects, roster_avg_age
            if isinstance(atmosphere, dict):
                self._crowd_energy = float(atmosphere.get("energy", 50.0))
                self._crowd_mood_home = float(atmosphere.get("mood", 30.0))
            away_age = roster_avg_age(self.away_team)
            hm, am = crowd_effects(self._crowd_energy, self._crowd_mood_home,
                                   away_avg_age=away_age)
            self._crowd_home_mult = hm
            self._crowd_away_mult = am
        except Exception:
            pass

    def _apply_homecoming_pregame(self):
        """Hostile homecomings (Wave C D39), the same shared pregame read
        GameSim uses (reputation_system.apply_homecoming_pregame): one
        decision, two fidelities. First-timers get the big moment (consumed
        here so it fires exactly once); simmering hate gets the smaller
        every-visit booing. The returnee's morale dings with it."""
        try:
            from reputation_system import apply_homecoming_pregame
            from arena_atmosphere import crowd_effects, roster_avg_age
            _hate = apply_homecoming_pregame(
                getattr(self, "rivalries", None) or [], self.home_team,
                self.away_team) or {}
            _changed = False
            for _hit in (_hate.get("first_timers") or []):
                _hp, _hr = _hit.get("player"), _hit.get("record") or {}
                self._crowd_energy = min(100.0, self._crowd_energy + 15.0)
                self._crowd_mood_home = min(100.0, self._crowd_mood_home + 10.0)
                _changed = True
                try:
                    _m = getattr(_hp, "morale", 70) or 70
                    _hp.morale = max(1, _m - min(6, 2 + int(
                        float(_hr.get("intensity", 0) or 0) // 25)))
                except Exception:
                    pass
            for _hit in (_hate.get("simmering") or []):
                _hp = _hit.get("player")
                _hi = float(_hit.get("intensity", 0) or 0)
                self._crowd_energy = min(100.0, self._crowd_energy + 6.0)
                self._crowd_mood_home = min(100.0, self._crowd_mood_home + 4.0)
                _changed = True
                try:
                    _m = getattr(_hp, "morale", 70) or 70
                    _hp.morale = max(1, _m - min(4, 1 + int(_hi // 30)))
                except Exception:
                    pass
            if _changed:
                away_age = roster_avg_age(self.away_team)
                hm, am = crowd_effects(self._crowd_energy,
                                       self._crowd_mood_home,
                                       away_avg_age=away_age)
                self._crowd_home_mult = hm
                self._crowd_away_mult = am
        except Exception:
            pass

    def _crowd_on_goal(self, scorer_team_name):
        """Live crowd swing after a goal; recompute the finishing mults."""
        try:
            from arena_atmosphere import (live_crowd_update, crowd_effects,
                                          roster_avg_age)
            _st = {"energy": self._crowd_energy, "mood": self._crowd_mood_home}
            live_crowd_update(
                _st, scorer_team_name == self.home_team.team_name,
                self.score.get(self.home_team.team_name, 0),
                self.score.get(self.away_team.team_name, 0),
                int(getattr(self, "period", 1) or 1))
            self._crowd_energy = _st["energy"]
            self._crowd_mood_home = _st["mood"]
            away_age = roster_avg_age(self.away_team)
            hm, am = crowd_effects(self._crowd_energy, self._crowd_mood_home,
                                   away_avg_age=away_age)
            self._crowd_home_mult = hm
            self._crowd_away_mult = am
        except Exception:
            pass

    def _apply_dressing_room_pregame(self):
        """Module 03: pre-game talks move the opening needle (both rooms).

        Each side's pending talk is consumed; AI clubs get an automatic
        coach talk through the same consume path the user's talks use, so
        user and AI share the mechanic. +/-1% finishing per talk point,
        capped at +/-4% -- a nudge, not a rewrite.
        """
        try:
            import dressing_room as _dr
            for team in (self.home_team, self.away_team):
                boost = _dr.consume_pregame_boost(team)
                name = team.team_name
                mult = self.dressing_boost.get(name, 1.0)
                if boost:
                    mult = max(0.96, min(1.04, mult + 0.01 * int(boost)))
                # One-game practice edge (bag-skate compete response): folds
                # into the same finishing channel, then zeroes.
                try:
                    dr = _dr.ensure_dressing_room_fields(team)
                    edge = float(dr.get("practice_edge", 0) or 0)
                    if edge:
                        mult = max(0.96, min(1.06, mult + edge))
                        dr["practice_edge"] = 0.0
                except Exception:
                    pass
                self.dressing_boost[name] = mult
        except Exception:
            pass

    def _apply_dressing_room_intermission(self):
        """Module 03: second-intermission words move the third-period needle."""
        try:
            import dressing_room as _dr
            diff = (self.score.get(self.home_team.team_name, 0)
                    - self.score.get(self.away_team.team_name, 0))
            for team, is_home in ((self.home_team, True),
                                  (self.away_team, False)):
                boost = _dr.consume_intermission_boost(
                    team, score_diff=diff if is_home else -diff)
                if boost:
                    name = team.team_name
                    self.dressing_boost[name] = max(
                        0.96, min(1.04,
                                  self.dressing_boost.get(name, 1.0)
                                  + 0.01 * int(boost)))
        except Exception:
            pass

    def _init_situations(self):
        """Per-team pre-game situational finishing edge (own channel).

        Compounds room state, coaching buy-in and youth hunger into one xG
        multiplier per side (+/-8% at the extremes). Computed ONCE per team
        per game here in __init__ -- the per-shot hot loop below only reads
        the stored multiplier, so the factor costs ~1ms per game total.
        Never raises; inert (1.0) when unused.
        """
        self._situation_edge = {
            self.home_team.team_name: 1.0, self.away_team.team_name: 1.0}
        self._situation_breakdown = {}
        try:
            from reputation_system import situations_factor as _sf
            _ctx = {"is_playoff": bool(getattr(self, "is_playoff", False))}
            for _team in (self.home_team, self.away_team):
                _bd = _sf(_team, _ctx)
                self._situation_breakdown[_team.team_name] = _bd
                self._situation_edge[_team.team_name] = float(
                    _bd.get("xg_mult", 1.0))
        except Exception:
            pass

    def _situation_edge_for(self, team_name: str) -> float:
        """Finishing multiplier for the attacking side from the situations
        factor. Read per shot; computed per game."""
        try:
            return self._situation_edge.get(team_name, 1.0)
        except Exception:
            return 1.0

    def _init_systems_edge(self):
        """Installed NHL systems (tactics.py): your attack vs their
        structure, your power play vs their kill. Computed ONCE per game
        here in __init__ -- the per-shot hot loop below only reads the
        stored multiplier. Never raises; inert (1.0) when unused."""
        self._systems_matchup = {"home_goals": 1.0, "away_goals": 1.0,
                                 "pace": 1.0, "home_pp": 1.0, "away_pp": 1.0,
                                 "home_sh_threat": 1.0,
                                 "away_sh_threat": 1.0,
                                 "home_shot_vol": 1.0, "away_shot_vol": 1.0,
                                 "home_shot_qual": 1.0, "away_shot_qual": 1.0}
        try:
            import tactics as _tx
            _tx.ensure_team_tactics(self.home_team)
            _tx.ensure_team_tactics(self.away_team)
            self._systems_matchup = _tx.matchup_modifiers(self.home_team,
                                                          self.away_team)
        except Exception:
            pass

    def _init_parity_edge(self):
        """Parity-engine multiplier per side, computed ONCE per game here
        in __init__ -- the per-shot hot loop below only reads the stored
        value. Same shared decision GameSim calls
        (parity_engine.pregame_multiplier); never raises."""
        self._parity_matchup = {"home": 1.0, "away": 1.0}
        try:
            import parity_engine as _pe
            _po = bool(getattr(self, "is_playoff", False))
            self._parity_matchup = {
                "home": _pe.pregame_multiplier(self.home_team,
                                               self.away_team,
                                               playoffs=_po),
                "away": _pe.pregame_multiplier(self.away_team,
                                               self.home_team,
                                               playoffs=_po),
            }
        except Exception:
            pass

    def _systems_edge_for(self, team_name: str) -> float:
        """Systems multiplier for the shooting side. Read per shot;
        computed per game. On the power play this is your PP system vs
        their kill (the defending kill used to be ignored entirely);
        shorthanded it folds in counterattack threat."""
        try:
            m = self._systems_matchup or {}
            home = team_name == self.home_team.team_name
            if getattr(self, "pp_team", None) == team_name:
                return m.get("home_pp" if home else "away_pp", 1.0)
            base = m.get("home_goals" if home else "away_goals", 1.0)
            # sh_threat lives on the VOLUME channel (divergence #15), not
            # here -- see _determine_event_type. (The PK side rarely shoots
            # in this engine's event model; the channel is unified for when
            # it does.)
            return base
        except Exception:
            return 1.0

    @staticmethod
    def _find_head_coach(team):
        """Head-coach staff object for pull-timing personality (None-safe)."""
        try:
            from game_classes import StaffRole
            found = team.get_staff_by_role(StaffRole.HEAD_COACH)
            return found[0] if found else None
        except Exception:
            return None

    def _select_lines(self, team_name, fatigue=False):
        fw, df, goalie, _fi, _di = self._select_lines_idx(team_name)
        return fw, df, goalie

    def _line_fatigue(self, team_name, line):
        """Mean accumulated fatigue of a line/pair (game-level, not shift).

        Mean, not total: a short-handed unit (injury, 1-man 4th line from
        a stored lineup) must not look artificially fresher than a full
        line just because it has fewer skaters accumulating fatigue.
        Empty lines are never selected.
        """
        members = [p for p in line if p]
        if not members:
            return float('inf')
        return (sum(self.stats[team_name].get(p.id, {}).get('fatigue', 0)
                    for p in members) / len(members))

    def _governor_state(self, team_name):
        """Wave A gradient-governor window for this team/game (seconds).

        Replaces the old binary 30-min skip (scoring calibration,
        2026-09-30 -- kept double-shifted stars at 37-47 min and 100-goal
        seasons out). The gradient bites from 24:00 to 30:00 and the
        backstop (38:00) still zeroes pathological cases, so the same
        protection holds without a learnable cliff. Short-bench games
        (<15 dressed skaters) shift the whole window up 4 minutes.
        Applies in OT too -- 3v3 rides the same two forwards, and an
        uncapped OT produced 52-min games; the backstop still binds.
        """
        try:
            from deployment_policy import (
                GOV_GRADIENT_START_S as _s,
                GOV_GRADIENT_FULL_S as _f,
                GOV_HARD_BACKSTOP_S as _b,
                GOV_SHORT_BENCH_SHIFT_S as _sh,
                _dressed_skater_count as _count,
            )
            try:
                _n = _count(self.lineups[team_name])
            except Exception:
                _n = 18
            _shift = _sh if _n < 15 else 0
            return _s + _shift, _f + _shift, _b + _shift
        except Exception:
            return 24 * 60, 30 * 60, 38 * 60

    def _line_governor_factor(self, team_name, line, state):
        """Wave A: gradient share-factor for this unit's binding skater
        (1.0 fresh -> 0.25 at full gradient bite -> 0.0 at the backstop).
        Mirrors deployment_policy.soft_cap_adjust_shares' full factor --
        TOI gradient x the shared condition governor
        (_condition_governor_mult) x the shared injury-risk governor
        (_injury_risk_governor_mult), all read off the same binding skater
        (max game TOI) GameSim's soft_cap_adjust_shares binds on. AdvGS
        tracks per-shift TOI and per-shift canonical energy (see
        _apply_shift_energy) instead of per-tick readings -- same decision,
        speed-optimized approximation. Fresh legs -> 1.0 x 1.0 x 1.0, so
        today's behavior is byte-identical when nobody is tired."""
        try:
            from deployment_policy import (
                _smoothstep as _ss,
                _condition_governor_mult as _cgm,
                _injury_risk_governor_mult as _rgm,
            )
            start_s, full_s, backstop_s = state
            _st = self.stats.get(team_name, {})
            worst = 0.0
            star = None
            for p in line or []:
                if not p:
                    continue
                try:
                    _t = float(_st.get(getattr(p, "id", None), {})
                               .get("toi", 0) or 0)
                    if _t > worst:
                        worst, star = _t, p
                except Exception:
                    continue
            if worst >= backstop_s:
                return 0.0
            if worst <= start_s:
                toi_g = 1.0
            else:
                bite = _ss((worst - start_s) / max(1.0, full_s - start_s))
                toi_g = 1.0 - 0.75 * bite
            # WS1 parity: the shared governors, same binding skater as
            # GameSim. Never raises (the shared functions return 1.0 on
            # failure); the 0.05 floor matches soft_cap_adjust_shares.
            cond_f = _cgm(star) if star is not None else 1.0
            risk_f = _rgm(star) if star is not None else 1.0
            return max(0.05, toi_g * cond_f * risk_f)
        except Exception:
            return 1.0

    def _apply_shift_energy(self, team_name, fw, df, shift_s=45.0):
        """WS1 parity: per-shift canonical energy accounting.

        Speed-optimized approximation of GameSim's per-tick energy loop
        (simulation._update_fatigue): on-ice skaters drain through the
        shared shift_energy_drain (same base rate, stamina term, PK/PP
        terms as the tick loop); benched skaters recover
        BENCH_RECOVERY_PER_S x fatigue_recovery_mult -- the D23 0.22/s
        bench regen at shift granularity. Both sides sync the canonical
        game_energy pool both fidelities' governors read. Goalies are
        excluded (own pool, never drained on this path). Never raises.
        """
        try:
            from condition_system import (
                shift_energy_drain as _drain,
                BENCH_RECOVERY_PER_S as _brs,
                fatigue_recovery_mult as _rec,
                get_game_energy as _ge,
                sync_game_energy as _sync,
            )
        except Exception:
            return
        try:
            team = (self.home_team
                    if team_name == self.home_team.team_name
                    else self.away_team)
            on_ice_ids = {getattr(p, "id", None)
                          for p in (fw or []) + (df or []) if p}
            on_ice_ids.discard(None)
            pk = (self.pk_team == team_name)
            pp = (self.pp_team == team_name)
            for p in getattr(team, "roster", None) or []:
                try:
                    if p is None:
                        continue
                    pos = getattr(p, "primary_position", None)
                    if getattr(pos, "name", "") == "GOALIE":
                        continue  # goalies have their own pool
                    cur = _ge(p)
                    if getattr(p, "id", None) in on_ice_ids:
                        new = max(0.0, cur - _drain(p, shift_s,
                                                   on_pk=pk, on_pp=pp))
                    else:
                        new = min(100.0,
                                  cur + _brs * _rec(p) * shift_s)
                    _sync(p, new)
                except Exception:
                    continue
        except Exception:
            pass

    def _select_lines_idx(self, team_name):
        """Least-fatigued unit. Returns (fw, df, goalie, fw_idx, df_idx).

        Wave A: the gradient governor deprioritizes (not hard-skips) units
        whose binding skater is deep in the gradient -- a unit at full
        bite skates as if ~2 shifts more tired (the same +6 scale as the
        matchup veto below). Only the pathological backstop zeroes a
        unit, and then the least-fatigued fallback still dresses a shift.
        """
        lineup = self.lineups[team_name]
        fw_lines = lineup['Forwards']
        df_pairs = lineup['Defense']
        goalies = lineup['Goalies']
        _gov = self._governor_state(team_name)

        # WS1 parity: the shared D17 condition->deployment read. GameSim's
        # _player_deployment_score multiplies every skater's weight by
        # condition_deployment_mult (gassed 0.85 / worn 0.94 / fresh 1.03,
        # playing hurt x0.90); AdvGS's quantity decision is the rotation
        # pick, so the line's mean shared mult scales its pick score the
        # same direction (worse condition -> picked later). Cached per
        # player id for the call -- persistent condition only moves between
        # games. Never raises.
        try:
            from condition_system import condition_deployment_mult as _cdm
        except Exception:
            _cdm = None
        _cdm_cache = {}

        def _line_cdm(_line):
            if _cdm is None:
                return 1.0
            _vals = []
            for _p in _line or []:
                if not _p:
                    continue
                _pid = getattr(_p, "id", None)
                if _pid not in _cdm_cache:
                    try:
                        _cdm_cache[_pid] = float(_cdm(_p))
                    except Exception:
                        _cdm_cache[_pid] = 1.0
                _vals.append(_cdm_cache[_pid])
            return sum(_vals) / len(_vals) if _vals else 1.0

        def _pick(lines):
            _best, _best_f = None, float("inf")
            _fb, _fb_f = None, float("inf")
            for i, _line in enumerate(lines):
                _f = self._line_fatigue(team_name, _line)
                _g = self._line_governor_factor(team_name, _line, _gov)
                _score = (_f + (1.0 - _g) * 8.0) / _line_cdm(_line)
                if _f < _fb_f:
                    _fb_f, _fb = _f, i
                if _g > 0.0 and _score < _best_f:
                    _best_f, _best = _score, i
            return _best if _best is not None else _fb

        fw_idx = _pick(fw_lines)
        df_idx = _pick(df_pairs)
        goalie = goalies[0] if goalies and goalies[0] else None
        return fw_lines[fw_idx], df_pairs[df_idx], goalie, fw_idx, df_idx

    def _last_change_response(self, away_f_idx, fresh_f, fresh_d):
        """Home's last-change answer to the away forward line (0-based).

        Delegates to the SHARED shift_engine.matching_response -- the same
        decision GameSim makes, with AdvGS's rotation pick as the roll
        context. Returns 0-based (want_f, want_d); a side equal to the
        fresh pick means "roll", not a directed matchup.
        """
        from shift_engine import matching_response as _mr
        prefs = getattr(self.home_team, "line_matchups", None) or {}
        want_f, want_d = _mr(away_f_idx + 1, prefs.get("F"), prefs.get("D"),
                             fresh_f + 1, fresh_d + 1)
        return want_f - 1, want_d - 1

    def _select_home_lines(self, team_name, away_f_idx):
        """Last change: answer the away declaration, with a fatigue veto.

        A coach won't send out dead legs for a matchup -- if the preferred
        unit is ~2 shifts more tired than the fresh pick, roll the fresh
        unit instead. Returns (fw, df, goalie, fw_idx, df_idx, directed).
        """
        fw, df, goalie, fresh_f, fresh_d = self._select_lines_idx(team_name)
        want_f, want_d = self._last_change_response(away_f_idx, fresh_f,
                                                    fresh_d)
        from shift_engine import matching_is_active as _mia
        prefs = getattr(self.home_team, "line_matchups", None) or {}
        act_f, act_d = _mia(away_f_idx + 1, prefs.get("F"), prefs.get("D"))
        lineup = self.lineups[team_name]
        fw_lines = lineup['Forwards']
        df_pairs = lineup['Defense']
        use_f, use_d, directed = fresh_f, fresh_d, False
        _gov = self._governor_state(team_name)
        if 0 <= want_f < len(fw_lines):
            if want_f == fresh_f:
                if act_f:
                    directed = True  # rotation already had the matchup unit
            elif (self._line_governor_factor(team_name, fw_lines[want_f], _gov) > 0.0
                    and self._line_fatigue(team_name, fw_lines[want_f])
                    <= self._line_fatigue(team_name, fw_lines[fresh_f]) + 6):
                use_f, directed = want_f, True
        if 0 <= want_d < len(df_pairs):
            if want_d == fresh_d:
                if act_d:
                    directed = True
            elif (self._line_governor_factor(team_name, df_pairs[want_d], _gov) > 0.0
                    and self._line_fatigue(team_name, df_pairs[want_d])
                    <= self._line_fatigue(team_name, df_pairs[fresh_d]) + 6):
                use_d, directed = want_d, True
        return fw_lines[use_f], df_pairs[use_d], goalie, use_f, use_d, directed

    # -- Goalie pull / 6-on-5 (parity with GameSim) --------------------------
    def _pull_eligible(self, team, team_name):
        """Late 3rd, trailing by 1-2, inside the coach's pull window, not
        shorthanded, not in OT. Timing via goalie_pull.pull_windows (coach
        style +- momentum risk); conversion untouched -- this is risk."""
        if self.period != 3:
            return False
        if team_name in self.goalie_pulled:
            return False
        other = (self.away_team.team_name if team is self.home_team
                 else self.home_team.team_name)
        diff = self.score[team_name] - self.score[other]
        if diff >= 0 or diff < -2:
            return False
        if self.pk_team == team_name:
            return False  # never shorthanded
        remaining = 3600 - self.time
        # Workstream B (2026-09-30): no phantom after-the-horn pulls -- a
        # pull needs live time on the clock.
        if remaining <= 0:
            return False
        try:
            from goalie_pull import pull_windows as _gpw
            d1, d2, _style = _gpw(self, team)
        except Exception:
            d1, d2 = 120, 60
        # OT drama, live lever: high-drama games pull earlier (extra
        # seconds on the coach's window). Conversion untouched -- risk.
        try:
            from ot_drama import pull_aggression_secs as _agg
            _a = _agg(getattr(self, "_drama_ctx", None))
            d1, d2 = d1 + _a, d2 + _a
        except Exception:
            pass
        deficit = -diff
        if deficit == 1 and remaining > d1:
            return False
        if deficit == 2 and remaining > d2:
            return False
        return True

    def _maybe_pull_goalies(self):
        """Once per shift: trailing teams pull for the extra attacker."""
        for team in (self.home_team, self.away_team):
            if self._pull_eligible(team, team.team_name):
                # RC3 parity (2026-10-01): GameSim pulls only with
                # possession in the OZ (NZ for the aggressive coach, DZ
                # never). AdvGS has no possession/zone state; the
                # fast-fidelity approximation is a per-shift opportunity
                # roll. A shift holds several puck-events, so P(an OZ
                # possession arises during the shift) is high: 0.65 for
                # balanced/conservative (OZ only), 0.80 for aggressive
                # (NZ gambles count). The style gate is the shared
                # goalie_pull.pull_style decision. A failed roll tries
                # again next shift -- the pull waits for its opportunity
                # instead of firing at the window's edge, but with a
                # 120s window the wait is short (GameSim pulls within
                # seconds of eligibility on a per-tick check).
                _pstyle = "balanced"
                try:
                    from goalie_pull import (pull_style as _pstyle_f,
                                             coach_for as _cfor_f)
                    _ps = _pstyle_f(_cfor_f(self, team))
                    _pstyle = (_ps.get("style", "balanced")
                               if isinstance(_ps, dict) else str(_ps))
                except Exception:
                    pass
                _opp_p = 0.80 if _pstyle == "aggressive" else 0.65
                if random.random() >= _opp_p:
                    continue
                _tn = team.team_name
                self._pull_goalie(_tn)
                # Structured drama (workstream B, 2026-09-30, additive):
                # record the strategic pull for measurement.
                try:
                    from drama_events import record_goalie_pull as _rgp
                    _style = "balanced"
                    try:
                        from goalie_pull import pull_windows as _gpw2
                        _, _, _style = _gpw2(self, team)
                        if isinstance(_style, dict):
                            _style = _style.get("style", "balanced")
                    except Exception:
                        pass
                    _oth = (self.away_team.team_name if team is self.home_team
                            else self.home_team.team_name)
                    _rem = 3600 - self.time
                    self._pull_clock[_tn] = round(max(0.0, _rem), 1)
                    _rgp(self, _tn, coach_style=_style,
                         deficit=self.score[_oth] - self.score[_tn])
                except Exception:
                    pass

    def _pull_goalie(self, team_name):
        if team_name in self.goalie_pulled:
            return
        self.goalie_pulled.add(team_name)
        self.on_ice[team_name]['Goalie'] = None
        self.events.append({'time': self.time, 'period': self.period,
                            'team': team_name, 'player': None,
                            'event': 'GoaliePulled'})

    def _return_goalie(self, team_name):
        self.goalie_pulled.discard(team_name)
        # Structured drama (workstream B): clear the live-pull tracking.
        try:
            self._pull_clock.pop(team_name, None)
        except Exception:
            pass

    def _return_all_goalies(self):
        self.goalie_pulled.clear()

    def _shift_fatigue_mult(self, team_name):
        """AdvancedGameSim adapter for the shared EHM fatigue curve."""
        try:
            from shift_engine import fatigue_curve as _fc
            return _fc(self._shift_age.get(team_name, 0.0))
        except Exception:
            return 1.0

    def _advance_time(self, seconds):
        self.time += seconds
        if self.time >= 1200 * self.period:
            old_period = self.period
            self.period += 1
            # D1 design build: benches re-evaluate between periods (same
            # shared decision as the watched path's intermission look).
            try:
                self._refresh_coach_instructions()
            except Exception:
                pass
            # The net is never empty across a horn.
            self._return_all_goalies()
            # WS1 parity: intermission breather -- the shared
            # INTERMISSION_RECOVERY x fatigue_recovery_mult both fidelities
            # apply between regulation periods
            # (GameSim._apply_intermission_recovery). Skaters only: goalies
            # have their own pool, never drained on this path. Never raises.
            if old_period in (1, 2):
                try:
                    from condition_system import (
                        INTERMISSION_RECOVERY as _ir,
                        fatigue_recovery_mult as _rec,
                        get_game_energy as _ge,
                        sync_game_energy as _sync,
                    )
                    for _t in (self.home_team, self.away_team):
                        for _p in getattr(_t, "roster", None) or []:
                            try:
                                _pos = getattr(_p, "primary_position", None)
                                if getattr(_pos, "name", "") == "GOALIE":
                                    continue
                                _sync(_p, min(100.0,
                                              _ge(_p) + _ir * _rec(_p)))
                            except Exception:
                                continue
                except Exception:
                    pass
            if old_period == 2 and self.period == 3:
                # Second intermission: dressing-room words move the
                # third-period needle (module 03).
                try:
                    self._apply_dressing_room_intermission()
                except Exception:
                    pass
            if self.period > 3 and self.score[self.home_team.team_name] == self.score[self.away_team.team_name]:
                self.period = 4
                self.time = 3600
            elif self.period > 4:
                self.time = 9999

    def _record_state(self):
        # Collect positions of all on-ice players and puck
        state = {
            'home': [
                {'id': p.id, 'x': p.x, 'y': p.y}
                for p in self.on_ice[self.home_team.team_name]['Forwards'] + self.on_ice[self.home_team.team_name]['Defense']
                if p
            ],
            'away': [
                {'id': p.id, 'x': p.x, 'y': p.y}
                for p in self.on_ice[self.away_team.team_name]['Forwards'] + self.on_ice[self.away_team.team_name]['Defense']
                if p
            ],
            'home_goalie': (
                {'id': self.on_ice[self.home_team.team_name]['Goalie'].id,
                 'x': self.on_ice[self.home_team.team_name]['Goalie'].x,
                 'y': self.on_ice[self.home_team.team_name]['Goalie'].y}
                if self.on_ice[self.home_team.team_name]['Goalie'] else None
            ),
            'away_goalie': (
                {'id': self.on_ice[self.away_team.team_name]['Goalie'].id,
                 'x': self.on_ice[self.away_team.team_name]['Goalie'].x,
                 'y': self.on_ice[self.away_team.team_name]['Goalie'].y}
                if self.on_ice[self.away_team.team_name]['Goalie'] else None
            ),
            'puck': {'x': self.puck_x, 'y': self.puck_y},
            'time': self.time,
            'period': self.period
        }
        self.state_history.append(state)

    def _simulate_shift(self):
        # Enhanced shift simulation for realistic hockey flow.
        # Last change: the away team declares its line first, the home
        # team answers (lines-screen "Match to line" prefs, else auto).
        home_name = self.home_team.team_name
        away_name = self.away_team.team_name
        away_f_idx, home_directed = 0, False
        for team_name in [away_name, home_name]:
            # EHM shift-fatigue: most shifts rotate the unit; sometimes a
            # unit gets stuck out (icing, extended pressure) and its
            # continuous age accumulates past the ~40s degradation onset.
            age = self._shift_age.get(team_name, 0.0)
            stuck = (age > 0.0 and self.on_ice[team_name]['Forwards']
                     and random.random() < 0.30)
            if stuck:
                fw = self.on_ice[team_name]['Forwards']
                df = self.on_ice[team_name]['Defense']
                g = self.on_ice[team_name]['Goalie']
                self._shift_age[team_name] = age + random.uniform(15, 30)
            elif team_name == home_name:
                fw, df, g, _fi, _di, home_directed = self._select_home_lines(
                    team_name, away_f_idx)
                self._shift_age[team_name] = random.uniform(30, 50)
            else:
                fw, df, g, away_f_idx, _di = self._select_lines_idx(team_name)
                self._shift_age[team_name] = random.uniform(30, 50)
            if team_name in self.goalie_pulled:
                g = None  # net empty: six attackers, no goalie on the ice
            # 3v3 overtime (divergence #3): two forwards + one defenseman,
            # the standard NHL OT unit -- not a full line.
            if getattr(self, "_ot_3v3", False):
                fw = [p for p in fw if p][:2]
                df = [p for p in df if p][:1]
            # Wave A gradient governor (player level): only the pathological
            # backstop (38:00, 42:00 short-bench) hard-sits a skater on a
            # "stuck" line that bypassed selection. The gradient already
            # deprioritized his unit at line selection, so this is the
            # last-resort brake -- never the cliff. Never empties a unit:
            # if all are at the backstop, the least-toied dresses.
            try:
                _gov = self._governor_state(team_name)
                if _gov is not None:
                    _st = self.stats.get(team_name, {})
                    _backstop = _gov[2]

                    def _toi_of(_p):
                        try:
                            return _st.get(getattr(_p, "id", None), {}).get("toi", 0)
                        except Exception:
                            return 0

                    def _cap_filter(_unit):
                        _live = [p for p in (_unit or []) if p]
                        if not _live:
                            return _unit
                        _ok = [p for p in _live if _toi_of(p) < _backstop]
                        if _ok:
                            return _ok
                        _live.sort(key=_toi_of)
                        return _live[:1]

                    fw = _cap_filter(fw)
                    df = _cap_filter(df)
            except Exception:
                pass
            self.on_ice[team_name]['Forwards'] = fw
            self.on_ice[team_name]['Defense'] = df
            self.on_ice[team_name]['Goalie'] = g
            for idx, p in enumerate(fw + df):
                if p:
                    # Defensive: ensure stat keys exist
                    if p.id not in self.stats[team_name]:
                        self.stats[team_name][p.id] = {'goals':0,'assists':0,'shots':0,'saves':0,'penalties':0,'toi':0,'fatigue':0}
                    self.stats[team_name][p.id]['toi'] += 45
                    self.stats[team_name][p.id]['fatigue'] += 1
            if g:
                if g.id not in self.stats[team_name]:
                    self.stats[team_name][g.id] = {'goals':0,'assists':0,'shots':0,'saves':0,'penalties':0,'toi':0,'fatigue':0}
                self.stats[team_name][g.id]['toi'] += 45
            # WS1 parity: per-shift canonical energy accounting (the 45s
            # shift matches the TOI credit above).
            self._apply_shift_energy(team_name, fw, df, shift_s=45.0)

        # Last-change edge for this shift: the home coach got his matchup,
        # the away's top line got checked. Small, on its own channel.
        self._matchup_edge[home_name] = 1.02 if home_directed else 1.0
        self._matchup_edge[away_name] = 0.99 if home_directed else 1.0
        # OT drama, live lever: in 3v3 OT the matchup tilt (coach personnel
        # choices + room/crowd edge) rides this channel instead.
        try:
            if getattr(self, "_ot_3v3", False):
                _tilt = float(getattr(self, "_ot_tilt", 0.0) or 0.0)
                if _tilt:
                    self._matchup_edge[home_name] = 1.0 + _tilt
                    self._matchup_edge[away_name] = 1.0 - _tilt
        except Exception:
            pass

        # Goalie-pull check (once per shift; period 3 only inside).
        self._maybe_pull_goalies()

        # Enhanced player movement with coordinate-based positioning
        for team_name in [self.home_team.team_name, self.away_team.team_name]:
            is_home_team = team_name == self.home_team.team_name
            
            for p in self.on_ice[team_name]['Forwards'] + self.on_ice[team_name]['Defense']:
                if p:
                    # Get current position from coordinate engine
                    current_pos = self.coordinate_engine.player_positions.get(p.id, (100, 42.5))
                    
                    # Determine target position based on game situation and player role
                    if hasattr(p, 'primary_position') and p.primary_position:
                        if 'WING' in str(p.primary_position):
                            # Wingers move along the boards and cycle
                            if is_home_team:
                                target_x = random.randint(120, 180)  # Attacking zone
                                target_y = random.choice([15, 70]) + random.randint(-8, 8)  # Wing positions
                            else:
                                target_x = random.randint(20, 80)   # Defending/neutral zone
                                target_y = random.choice([15, 70]) + random.randint(-8, 8)
                        elif 'CENTER' in str(p.primary_position):
                            # Centers control the middle of the ice
                            if is_home_team:
                                target_x = random.randint(110, 170)  # Attacking area
                            else:
                                target_x = random.randint(30, 90)   # Defensive area
                            target_y = 42.5 + random.randint(-15, 15)  # Central corridor
                        else:  # Defense
                            # Defensemen stay back unless rushing
                            rush_chance = 0.15 if random.random() < 0.15 else 0
                            if is_home_team:
                                if rush_chance:
                                    target_x = random.randint(140, 160)  # Offensive rush
                                else:
                                    target_x = random.randint(80, 120)   # Stay back
                            else:
                                if rush_chance:
                                    target_x = random.randint(40, 60)    # Offensive rush  
                                else:
                                    target_x = random.randint(80, 120)   # Stay back
                            target_y = 42.5 + random.randint(-20, 20)
                    else:
                        # Fallback positioning
                        target_x = current_pos[0] + random.randint(-15, 15)
                        target_y = current_pos[1] + random.randint(-8, 8)
                    
                    # Ensure target is within rink bounds
                    target_x = max(5, min(195, target_x))
                    target_y = max(5, min(80, target_y))
                    target_pos = (target_x, target_y)
                    
                    # Generate realistic movement events
                    movement_events = self.coordinate_engine.simulate_player_movement(
                        p.id, target_pos, "skate"
                    )
                    
                    # Add movement events to event log
                    for event in movement_events:
                        event['timestamp'] = self.time + event['timestamp']
                        self.event_log.append(event)
                    
                    # Update legacy position tracking for compatibility
                    p.x, p.y = target_pos
        
        # Generate realistic events per shift (reduced from 6-12 to 2-4 for performance)
        num_events = random.randint(2, 4)  # Reduced event count for better performance
        for _ in range(num_events):
            self._simulate_event()
            # Slightly larger time increments between events
            self._advance_time(random.randint(8, 15))  # 8-15 seconds between events
            
        # Final shift time advancement (remaining time)
        remaining_time = 45 - (num_events * 10)  # Approximate remaining time
        if remaining_time > 0:
            self._advance_time(remaining_time)
        self._record_state()

    def _simulate_event(self):
        puck_team_name = self.home_team.team_name if random.random() < 0.5 else self.away_team.team_name
        # 6-on-5 (workstream B, 2026-09-30): the pulled-goalie unit camps in
        # the zone -- the shared OZ-sustenance fidelity for this engine
        # weights puck-event retention toward the pulling team (personnel-
        # scaled, ~0.56-0.78), replacing the 50/50 coin flip. The power-play
        # override below still takes precedence when both apply.
        try:
            _gp65 = set(getattr(self, "goalie_pulled", set()) or set())
            if _gp65 and puck_team_name not in _gp65:
                from six_on_five import oz_possession_retention as _ret65
                _pteam = (self.home_team if puck_team_name == self.home_team.team_name
                          else self.away_team)
                _pull_tn = next(iter(_gp65))
                _pull_team = (self.home_team if _pull_tn == self.home_team.team_name
                              else self.away_team)
                if _pull_team is not _pteam:
                    _po = self.on_ice.get(_pull_tn, {}) or {}
                    _pu65 = [p for p in (_po.get("Forwards", [])
                                         + _po.get("Defense", [])) if p]
                    _do = self.on_ice.get(puck_team_name, {}) or {}
                    _du65 = [p for p in (_do.get("Forwards", [])
                                         + _do.get("Defense", [])) if p]
                    if random.random() < _ret65(_pu65, _du65):
                        puck_team_name = _pull_tn
        except Exception:
            pass
        opp_team_name = self.away_team.team_name if puck_team_name == self.home_team.team_name else self.home_team.team_name
        if self.pp_team:
            puck_team_name = self.pp_team
            opp_team_name = self.pk_team
        shooters = [p for p in self.on_ice[puck_team_name]['Forwards'] + self.on_ice[puck_team_name]['Defense'] if p]
        if not shooters:
            return
        # ONE decision (divergence #14): the shared shooter-choice weight
        # (archetype shoot tendency x shot_frequency_mult, flattened) --
        # the same number GameSim uses. Replaces the old overall_rating
        # weighting.
        from player_archetypes import shooter_choice_weight as _scw
        # Shot-volume realism (2026-09-30, Muck): one puck, shared with
        # linemates. Parity with GameSim (simulation.py: the shooter
        # weight is cut x0.35 when the player is in _recent_shooters) --
        # you just shot, the puck moves on. A weight, not a cap: a
        # generational talent in a perfect season can still spike, but
        # one man can't take every shot of his line's chances anymore.
        _recent = self._recent_shooters.get(puck_team_name)

        def _shooter_w(_p):
            try:
                _w = float(_scw(_p))
            except Exception:
                _w = 1.0
            try:
                if _recent is not None and getattr(_p, "id", None) in _recent:
                    _w *= 0.35
            except Exception:
                pass
            # PP micro-rotation (2026-09-30, Muck): heaters get better
            # looks WITHIN the unit — bounded share tilt, mean 1.0, never
            # changes who dresses. Same shared helper GameSim uses.
            try:
                if self.pp_team and getattr(self, "_lc_look", None):
                    _w *= self._lc_look.get(getattr(_p, "id", None), 1.0)
            except Exception:
                pass
            return _w

        # Lazily (re)compute the PP look shares when the unit changes.
        try:
            if self.pp_team:
                from line_chemistry import pp_look_shares as _lpls
                _ukey = (self.pp_team,
                         frozenset(getattr(p, "id", None) for p in shooters))
                if getattr(self, "_lc_look_key", None) != _ukey:
                    _tm = (self.home_team
                           if puck_team_name == self.home_team.team_name
                           else self.away_team)
                    self._lc_look = _lpls(shooters, sim=self, team=_tm)
                    self._lc_look_key = _ukey
            else:
                self._lc_look = None
                self._lc_look_key = None
        except Exception:
            pass

        shooter = random.choices(shooters,
                                 weights=[_shooter_w(p) for p in shooters],
                                 k=1)[0]
        try:
            if _recent is not None:
                _recent.append(getattr(shooter, "id", None))
        except Exception:
            pass
        goalie = self.on_ice[opp_team_name]['Goalie']

        # --- Enhanced Fatigue System ---
        fatigue_factor = self._calculate_fatigue_factor(shooter, puck_team_name)
        
        # --- Pressure Situations ---
        pressure_modifier = self._calculate_pressure_modifier(shooter)
        
        # --- Position and Formation Factors ---
        position_factor = self._calculate_position_factor(shooter, puck_team_name)
        
        # --- Determine Event Type based on player attributes ---
        _puck_team = (self.home_team if puck_team_name == self.home_team.team_name
                      else self.away_team)
        event_type = self._determine_event_type(shooter, shooters, fatigue_factor,
                                                team=_puck_team,
                                                opp_team_name=opp_team_name)
        
        if event_type == "SHOT":
            self._resolve_shot_event(shooter, goalie, puck_team_name, opp_team_name, fatigue_factor, pressure_modifier, position_factor, shooters)
        elif event_type == "PASS":
            self._resolve_pass_event(shooter, shooters, puck_team_name, opp_team_name, fatigue_factor)
        elif event_type == "DEKE":
            self._resolve_deke_event(shooter, puck_team_name, fatigue_factor)
        elif event_type == "PUCK_BATTLE":
            self._resolve_puck_battle(shooters, puck_team_name, fatigue_factor)
        elif event_type == "SCREEN":
            self._resolve_screen_event(shooter, shooters, puck_team_name)
        elif event_type == "DEFLECTION":
            self._resolve_deflection_event(shooter, shooters, goalie, puck_team_name, opp_team_name)
            
        # --- Random penalty check with improved logic ---
        self._check_for_penalty(shooters, puck_team_name, opp_team_name, fatigue_factor)
        
        # --- End power play when the 2-minute penalty clock expires ---
        if self.pp_team and self.pp_end_time and self.time >= self.pp_end_time:
            self.pp_team = None
            self.pk_team = None
            self.pp_end_time = None
        self._record_state()
        
        # Don't advance time here - it's managed in _simulate_shift
        self._record_state()






    def _calculate_fatigue_factor(self, player, team_name):
        """Calculate comprehensive fatigue factor"""
        player_fatigue = self.stats[team_name][player.id].get('fatigue', 0)
        endurance = getattr(player, 'endurance', 10)
        stamina = getattr(player, 'stamina', 10)
        durability = getattr(player, 'durability', 10)
        
        # Better players with high endurance/stamina maintain performance longer
        fatigue_resistance = (endurance + stamina + durability) / 3
        fatigue_factor = 1.0 - min(0.6, player_fatigue / max(1, fatigue_resistance))
        return max(0.4, fatigue_factor)  # Never go below 40% performance
    
    def _calculate_pressure_modifier(self, player):
        """Calculate how player performs under pressure"""
        pressure_rating = getattr(player, 'pressure_player', 10)
        composure = getattr(player, 'composure', 10)
        confidence = getattr(player, 'confidence', 10)
        determination = getattr(player, 'determination', 10)
        
        # Close games and late periods increase pressure
        score_diff = abs(self.score[self.home_team.team_name] - self.score[self.away_team.team_name])
        is_late_game = self.period >= 3 and self.time > 3000
        is_close_game = score_diff <= 1
        
        pressure_level = 1.0
        if is_late_game and is_close_game:
            pressure_level = 1.3
        elif is_close_game:
            pressure_level = 1.1
            
        pressure_skill = (pressure_rating + composure + confidence + determination) / 4
        pressure_modifier = 1.0 + (pressure_skill - 10) * 0.02 * pressure_level
        return max(0.7, min(1.4, pressure_modifier))
    
    def _calculate_position_factor(self, player, team_name):
        """Calculate positional advantage/disadvantage"""
        off_the_puck = getattr(player, 'off_the_puck', 10)
        anticipation = getattr(player, 'anticipation', 10)
        hockey_iq = getattr(player, 'hockey_iq', 10)
        
        # Players with better off-the-puck movement get better opportunities
        position_skill = (off_the_puck + anticipation + hockey_iq) / 3
        return 1.0 + (position_skill - 10) * 0.03
    
    def _pp_forecheck_sustenance(self):
        """Shared PP zone-sustenance for the WS4 zone hooks (fast fidelity).

        Returns line_chemistry.pp_zone_sustenance for the on-ice 5-man PP
        unit (0.75..1.25 from formation completeness), or 1.0 when no PP
        is running. The same shared function the watched path calls on
        its forecheck/keep-in/strip hooks -- one decision, two fidelities.
        Never raises.
        """
        try:
            _pp_tn = getattr(self, "pp_team", None)
            if _pp_tn is None:
                return 1.0
            from line_chemistry import pp_zone_sustenance as _pzs_h
            _onice = getattr(self, "on_ice", {}).get(_pp_tn, {}) or {}
            _unit = []
            for _slot, _pl in _onice.items():
                if _slot == "Goalie":
                    continue
                # on_ice slots hold lists (Forwards/Defense), not players
                if isinstance(_pl, (list, tuple)):
                    _unit.extend([p for p in _pl if p is not None])
                elif _pl is not None:
                    _unit.append(_pl)
            if not _unit:
                return 1.0
            _tm = (self.home_team
                   if _pp_tn == self.home_team.team_name else self.away_team)
            return float(_pzs_h(_unit, sim=self, team=_tm))
        except Exception:
            return 1.0

    def _determine_event_type(self, player, shooters, fatigue_factor, team=None,
                                opp_team_name=None):
        """Determine what type of event occurs based on player attributes"""
        creativity = getattr(player, 'creativity', 10)
        decision_making = getattr(player, 'decision_making', 10)
        stickhandling = getattr(player, 'stickhandling', 10)
        passing = getattr(player, 'passing', 10)
        
        # Base probabilities - tuned for realistic NHL game flow
        # Target: ~70-75 shot attempts from ~225 events per game (~32% shots)
        # Hockey is mostly passing and puck battles, not constant shooting
        shot_prob = 0.32
        pass_prob = 0.40 if len(shooters) > 1 else 0.0
        deke_prob = 0.08
        battle_prob = 0.12
        screen_prob = 0.05
        deflection_prob = 0.03
        
        # Modify based on attributes
        if creativity > 15:
            deke_prob *= 1.5
            pass_prob *= 1.2
        if decision_making > 15:
            pass_prob *= 1.3
        if stickhandling > 15:
            deke_prob *= 1.4
        if passing > 15:
            pass_prob *= 1.3
            
        # Fatigue reduces creative plays -- and, per the unified channel
        # decision (GameSim canonical), shot VOLUME, not conversion.
        # Conversion-side fatigue lives in the impact tier, not here.
        deke_prob *= fatigue_factor
        pass_prob *= fatigue_factor
        shot_prob *= fatigue_factor

        # -- Perfect mesh (additive): aligned units create more -- the extra
        # pass, the extra look, the assist that wins the game. A guy doesn't
        # need a hat trick to have his night. Half the conversion effect.
        try:
            from mesh_system import mesh_chance_factor as _mesh_chance
            _mates = [p for p in shooters if p is not player]
            _cf = _mesh_chance(player, _mates, team,
                               is_playoff=bool(getattr(self, "is_playoff", False)))
            if _cf != 1.0:
                shot_prob *= _cf
                pass_prob *= _cf
        except Exception:
            pass

        # -- Installed NHL systems (tactics.py): zone modules drive shot
        # volume team-by-team -- swarm/rush/net-front teams shoot more,
        # trap teams shoot less. Dynamic per team, per game. SHOT_LIFT
        # raises the league to real NHL volume (~29.5 SOG/team/game).
        #
        # 3v3 overtime (divergence #3, workstream B(e)): the open ice is
        # worth 2.00x shot volume -- the same decision GameSim's
        # THREE_ON_THREE branch makes in _apply_situation_modifiers.
        # The live lever for (e), with the ot_3v3_tilt on grade below.
        if getattr(self, "_ot_3v3", False):
            shot_prob *= 2.50
        # 6-on-5 (divergence #13, workstream B, 2026-09-30): the pulled-goalie
        # extra attacker. The flat 2.2x is replaced by the shared
        # generation-side 6v5 model (six_on_five.six_on_five_volume): the
        # six-man unit's personnel-scaled volume edge (net-front/shooting/
        # IQ vs the defense's box-out, ~1.30-1.90). Same decision GameSim
        # makes on its volume gate -- one decision, two fidelities.
        # (No conversion boost on either side.)
        try:
            if (team is not None and getattr(team, "team_name", "")
                    in getattr(self, "goalie_pulled", set())):
                from six_on_five import six_on_five_volume as _v65
                _tn65 = team.team_name
                _a_on65 = self.on_ice.get(_tn65, {}) or {}
                _a_u65 = [p for p in (_a_on65.get("Forwards", [])
                                      + _a_on65.get("Defense", []))
                          if p is not None]
                _opp65 = (self.away_team if team is self.home_team
                          else self.home_team)
                _d_on65 = self.on_ice.get(_opp65.team_name, {}) or {}
                _d_u65 = [p for p in (_d_on65.get("Forwards", [])
                                      + _d_on65.get("Defense", []))
                          if p is not None]
                shot_prob *= _v65(_a_u65, _d_u65)
        except Exception:
            pass
        # sh_threat (divergence #15): unified on the VOLUME channel. An
        # aggressive kill hunts shorthanded rushes (more shots), a passive
        # box just survives -- the same 0.7 + 0.3*sh_threat shape GameSim
        # uses in _apply_situation_modifiers. (Conversion side: none.)
        try:
            if team is not None:
                _tn15 = getattr(team, "team_name", "")
                if getattr(self, "pk_team", None) == _tn15:
                    _m15 = self._systems_matchup or {}
                    _h15 = _tn15 == self.home_team.team_name
                    _sh15 = _m15.get("home_sh_threat" if _h15
                                     else "away_sh_threat", 1.0)
                    shot_prob *= 0.7 + 0.3 * _sh15
        except Exception:
            pass
        try:
            _m = self._systems_matchup or {}
            _h = (team is not None and getattr(team, "team_name", "")
                  == self.home_team.team_name)
            _sv = _m.get("home_shot_vol" if _h else "away_shot_vol", 1.0)
            import tactics as _txl
            shot_prob *= _sv * _txl.SHOT_LIFT
            # Pace (divergence #6): GameSim scales volume by the geometric
            # mean of both teams' tempo; the matchup precomputes exactly
            # that number -- apply it here on the volume gate, same channel.
            try:
                shot_prob *= _m.get("pace", 1.0)
            except Exception:
                pass
            # NOTE: parity lives on CONVERSION (divergence #8), not here.
            # GameSim applies pregame_multiplier on shot quality; this
            # engine applies it on shot_chance in _resolve_shot_event.
            # Rush identity: rush teams shoot off the rush instead of
            # taking the extra pass -- shift mass pass -> shot.
            _rush = _m.get("home_rush" if _h else "away_rush", 1.0)
            if _rush != 1.0:
                _rshift = pass_prob * (1.0 - 1.0 / _rush)
                _rshift = max(-shot_prob * 0.5,
                              min(pass_prob * 0.5, _rshift))
                pass_prob -= _rshift
                shot_prob += _rshift
        except Exception:
            pass
        
        # PP formation completeness (shared channel with GameSim): a
        # well-structured 5-man unit sustains OZ time and generates volume;
        # a malformed one bleeds it. The same pp_zone_sustenance the
        # watched path uses on its forecheck/keep-in/strip hooks, applied
        # here on the shot-volume gate. Volume channel only.
        try:
            _pp_tn = getattr(self, "pp_team", None)
            if (_pp_tn is not None and team is not None
                    and getattr(team, "team_name", "") == _pp_tn):
                from line_chemistry import pp_zone_sustenance as _pzs_qs
                _onice_qs = getattr(self, "on_ice", {}).get(_pp_tn, {})
                _unit_qs = []
                for _slot, _pl in _onice_qs.items():
                    if _slot == "Goalie":
                        continue
                    # on_ice slots hold lists (Forwards/Defense), not players
                    if isinstance(_pl, (list, tuple)):
                        _unit_qs.extend([p for p in _pl if p is not None])
                    elif _pl is not None:
                        _unit_qs.append(_pl)
                if _unit_qs:
                    _tm_qs = self.home_team if _pp_tn == self.home_team.team_name else self.away_team
                    shot_prob *= _pzs_qs(_unit_qs, sim=self, team=_tm_qs)
        except Exception:
            pass

        # WS4 H2 -- NZ forecheck strip (GameSim simulation.py:2957, fast
        # fidelity): the 5-man PP hunts the puck in the neutral zone and
        # strips re-entries, manufacturing 1v1 transition looks back the
        # other way. A well-structured unit (sustenance > 1) creates more
        # deke/rush chances; a malformed one fewer. Event-mix channel --
        # the scenario battle on resolution (WS4 gap 1) decides the 1v1,
        # this only decides how often the forecheck earns the look.
        try:
            _pp_tn2 = getattr(self, "pp_team", None)
            if (_pp_tn2 is not None and team is not None
                    and getattr(team, "team_name", "") == _pp_tn2):
                deke_prob *= self._pp_forecheck_sustenance()
        except Exception:
            pass

        # D1 design build: coach instructions move the volume gate -- the
        # fast fidelity of the watched path's rush nudges (same shared
        # effects). Own instruction scales own shot volume; the
        # opponent's defensive instruction suppresses it; crash_net adds
        # net-front presence (screens up -- the deflection else-branch
        # rides along).
        try:
            _tn = getattr(team, "team_name", "") if team is not None else ""
            if _tn:
                shot_prob *= self._instruction_effect(
                    _tn, "shot_volume_mult", 1.0)
                screen_prob *= self._instruction_effect(
                    _tn, "netfront_event_mult", 1.0)
            if opp_team_name:
                shot_prob *= self._instruction_effect(
                    opp_team_name, "opp_shot_volume_mult", 1.0)
        except Exception:
            pass

        # Random selection based on probabilities
        rand = random.random()
        if rand < shot_prob:
            return "SHOT"
        elif rand < shot_prob + pass_prob:
            return "PASS"
        elif rand < shot_prob + pass_prob + deke_prob:
            return "DEKE"
        elif rand < shot_prob + pass_prob + deke_prob + battle_prob:
            return "PUCK_BATTLE"
        elif rand < shot_prob + pass_prob + deke_prob + battle_prob + screen_prob:
            return "SCREEN"
        else:
            return "DEFLECTION"

    def run(self):
        # NHL rules: 5-minute 3v3 sudden-death OT, then shootout
        overtime_limit = 300  # 5 minutes OT (NHL regular season)
        shootout_rounds = 3  # Initial shootout rounds, then sudden death
        # D11: fresh game -> fresh per-unit block cache.
        try:
            self._block_unit_cache = {}
        except Exception:
            pass

        # OT drama (ot_drama, additive): the live levers (pull aggression,
        # OT matchup tilt, shootout edge) read this context. OT itself is
        # always the flat NHL 300 seconds -- drama moves who wins it, not
        # how long it lasts. No league -> exactly today's behavior.
        _ot_ctx = None
        if getattr(self, "league", None) is not None:
            try:
                from ot_drama import ot_context
                _ot_ctx = ot_context(
                    self.home_team, self.away_team, league=self.league,
                    atmosphere={"energy": getattr(self, "_crowd_energy", 50.0)})
            except Exception:
                _ot_ctx = None
        self._drama_ctx = _ot_ctx

        # Fresh game: no stale last-passer carried over from a previous game
        for _t in (self.home_team, self.away_team):
            for _p in getattr(_t, 'roster', []) or []:
                try:
                    _p.assist_potential = None
                except Exception:
                    pass

        # Regulation: 60 minutes
        while self.time < 3600:
            self._simulate_shift()

        # Overtime: 3v3 sudden death - first goal wins (divergence #3:
        # GameSim skates 3v3; this engine used to run full-strength OT).
        if self.score[self.home_team.team_name] == self.score[self.away_team.team_name]:
            ot_start = self.time
            ot_home_start = self.score[self.home_team.team_name]
            ot_away_start = self.score[self.away_team.team_name]
            self.period = 4
            self._ot_3v3 = True
            # OT drama, live lever (ot_drama): 3v3 matchup choices. The
            # coach's personnel acumen + room/crowd edge tilt OT finishing
            # a touch, on the existing matchup channel (shot_chance mult).
            try:
                from ot_drama import ot_matchup_tilt as _omt
                self._ot_tilt = _omt(
                    getattr(self, "_drama_ctx", None),
                    home_coach=getattr(self, "_home_coach", None),
                    away_coach=getattr(self, "_away_coach", None))
            except Exception:
                self._ot_tilt = 0.0
            try:
                while (self.time < ot_start + overtime_limit and
                       self.score[self.home_team.team_name] == self.score[self.away_team.team_name]):
                    self._simulate_shift()
                    # Sudden death: stop immediately on goal
                    # (The loop condition checks the tie each iteration)
            finally:
                self._ot_3v3 = False
                self._ot_tilt = 0.0
            
            # Enforce true sudden death: max 1 goal per team in OT
            # (A shift might generate multiple goals before the loop checks)
            home_ot_goals = self.score[self.home_team.team_name] - ot_home_start
            away_ot_goals = self.score[self.away_team.team_name] - ot_away_start
            if home_ot_goals > 1:
                self.score[self.home_team.team_name] = ot_home_start + 1
            if away_ot_goals > 1:
                self.score[self.away_team.team_name] = ot_away_start + 1
            # Structured drama (workstream B, 2026-09-30, additive): OT was
            # decided live in 3v3 sudden death (regular season here).
            try:
                from drama_events import record_ot_result as _rot_q
                if (self.score[self.home_team.team_name] > ot_home_start
                        or self.score[self.away_team.team_name] > ot_away_start):
                    if self.score[self.home_team.team_name] > self.score[self.away_team.team_name]:
                        _rot_q(self, "3v3", self.home_team.team_name, self.away_team.team_name)
                    else:
                        _rot_q(self, "3v3", self.away_team.team_name, self.home_team.team_name)
            except Exception:
                pass
        # If still tied after OT, do shootout

        # Defensive: get home/away goalies safely
        def get_goalie(team, lineup):
            goalies = lineup.get('Goalies', [])
            if goalies and goalies[0]:
                return goalies[0]
            # Fallback: pick a random goalie from roster
            candidates = [p for p in team.roster if getattr(p, 'primary_position', None) and p.primary_position.name == "GOALIE"]
            return candidates[0] if candidates else None

        home_goalie = get_goalie(self.home_team, self.lineups[self.home_team.team_name])
        away_goalie = get_goalie(self.away_team, self.lineups[self.away_team.team_name])

        if self.score[self.home_team.team_name] == self.score[self.away_team.team_name]:
            # Shootout: 3 rounds, then sudden-death rounds until winner
            # NHL rule: shootout winner is credited with +1 goal
            home_goals = 0
            away_goals = 0
            
            # Get shooters (cycle through forwards if needed for sudden death)
            home_forwards = [p for line in self.lineups[self.home_team.team_name].get('Forwards', []) for p in line if p]
            away_forwards = [p for line in self.lineups[self.away_team.team_name].get('Forwards', []) for p in line if p]
            
            def shootout_attempt(shooter, goalie, team_name):
                """Single shootout attempt. Returns True if goal scored.

                ONE decision: the shared player_traits core -- the same
                skill-roll + traits resolution GameSim uses. The old
                0.33 + linear formula is retired. ot_drama may add a small
                edge via the optional parameter (default 0.0 = today's
                behavior exactly).
                """
                from player_traits import resolve_shootout_attempt as _so
                _edge = 0.0
                if _ot_ctx is not None:
                    try:
                        from ot_drama import shootout_edge as _se
                        _edge = _se(
                            _ot_ctx,
                            shooter_is_home=(team_name == self.home_team.team_name))
                    except Exception:
                        _edge = 0.0
                if _so(shooter, goalie, edge=_edge):
                    self.events.append({'time': self.time, 'period': 5, 'team': team_name, 'player': shooter, 'event': 'Shootout Goal'})
                    return True
                return False
            
            # Initial 3 rounds
            round_num = 0
            for i in range(shootout_rounds):
                round_num += 1
                if i < len(home_forwards):
                    if shootout_attempt(home_forwards[i], away_goalie, self.home_team.team_name):
                        home_goals += 1
                if i < len(away_forwards):
                    if shootout_attempt(away_forwards[i], home_goalie, self.away_team.team_name):
                        away_goals += 1
            
            # Sudden death rounds if tied (NHL rule)
            sudden_death_round = 0
            while home_goals == away_goals and sudden_death_round < 20:  # Safety cap
                sudden_death_round += 1
                # Cycle through shooters
                home_shooter = home_forwards[(shootout_rounds + sudden_death_round - 1) % max(1, len(home_forwards))] if home_forwards else None
                away_shooter = away_forwards[(shootout_rounds + sudden_death_round - 1) % max(1, len(away_forwards))] if away_forwards else None
                
                home_scored = shootout_attempt(home_shooter, away_goalie, self.home_team.team_name) if home_shooter else False
                away_scored = shootout_attempt(away_shooter, home_goalie, self.away_team.team_name) if away_shooter else False
                
                if home_scored:
                    home_goals += 1
                if away_scored:
                    away_goals += 1
                
                # In sudden death, if one scores and the other doesn't, it's over
                # (both scored or both missed = continue)
                if home_scored != away_scored:
                    break
            
            # Determine winner (no more auto-win for away on tie - sudden death ensures a winner)
            if home_goals > away_goals:
                winner, loser = self.home_team, self.away_team
                # NHL: shootout winner credited with +1 goal
                self.score[self.home_team.team_name] += 1
            elif away_goals > home_goals:
                winner, loser = self.away_team, self.home_team
                self.score[self.away_team.team_name] += 1
            else:
                # Extremely rare: still tied after 20 sudden death rounds
                # Home team wins coin flip (better than auto-away-win)
                winner, loser = self.home_team, self.away_team
                self.score[self.home_team.team_name] += 1
            
            scores = (self.score[self.home_team.team_name], self.score[self.away_team.team_name])
            notable_events = [e for e in self.events if e['event'] == 'Goal' or e['event'] == 'Shootout Goal']
            # Structured drama (workstream B, 2026-09-30, additive).
            try:
                from drama_events import record_ot_result as _rot_q2
                _rot_q2(self, "shootout", winner.team_name, loser.team_name)
            except Exception:
                pass
            self._record_mesh_performances()
            # Shootout => the game went past regulation.
            self._record_parity_result(winner, scores, went_ot=True)
            self._persist_analytics_game(scores)
            return winner, loser, scores, self.events, notable_events
        if self.score[self.home_team.team_name] > self.score[self.away_team.team_name]:
            winner, loser = self.home_team, self.away_team
        else:
            winner, loser = self.away_team, self.home_team
        scores = (self.score[self.home_team.team_name], self.score[self.away_team.team_name])
        notable_events = [e for e in self.events if e['event'] == 'Goal']
        
        # Gameplay injuries: small chance per game (NHL: ~1 injury per 3-4 games)
        self._process_gameplay_injuries()
        self._record_mesh_performances()
        self._record_parity_result(winner, scores,
                                   went_ot=self.period > 3)
        self._persist_analytics_game(scores)

        return winner, loser, scores, self.events, notable_events

    def _persist_analytics_game(self, scores):
        """Persist the lightweight shot log for the Analytics Hub
        (module 04). Analytics integration (2026-10-01): quick_sim never
        fed the hub -- now each game appends a record in the same shape
        GameSim writes (shots with grade/xg/chance_context, score tuple),
        capped at 10 per team. Additive; never raises; never touches
        engine state.
        """
        try:
            _shots = list(getattr(self, "_analytics_shots", None) or [])
            _rec = {
                "date": "",
                "home": getattr(self.home_team, "team_name", ""),
                "away": getattr(self.away_team, "team_name", ""),
                "score": (int(scores[0]), int(scores[1])) if scores else (0, 0),
                "shots": _shots,
                "entries": [],
                "momentum": [],
                "engine": "quick_sim",
            }
            for _team in (self.home_team, self.away_team):
                try:
                    _lst = list(getattr(_team, "analytics_games", None) or [])
                    _lst.append(_rec)
                    del _lst[:-10]
                    _team.analytics_games = _lst
                except Exception:
                    pass
        except Exception:
            pass

    def _record_parity_result(self, winner, scores, went_ot=False):
        """Feed the finished result into the parity engine (cross-game team
        form + season table). Additive; never raises; never touches stats."""
        try:
            import parity_engine as _pe
            _pe.record_result(
                self.home_team, self.away_team,
                winner == self.home_team, went_ot=bool(went_ot))
        except Exception:
            pass

    def _record_mesh_performances(self):
        """Feed finished-game lines into the mesh form tracker (moments ->
        streaks -> breakouts). Additive: never touches existing stat flow."""
        try:
            from mesh_system import record_performance
            is_po = bool(getattr(self, "is_playoff", False))
            for team in (self.home_team, self.away_team):
                tstats = self.stats.get(team.team_name, {})
                by_id = {pl.id: pl for pl in (getattr(team, 'roster', []) or [])}
                for pid, ps in tstats.items():
                    pl = by_id.get(pid)
                    if pl is None:
                        continue
                    # Goalies: feed saves/shots-against so the last-10
                    # performance ledger grades on save% (Muck 2026-10-01).
                    _sv = ps.get('saves', 0) or 0
                    _ga = ps.get('goals_against', 0) or 0
                    note = record_performance(
                        pl, ps.get('goals', 0), ps.get('assists', 0),
                        team=team, is_playoff=is_po,
                        saves=_sv, shots_against=_sv + _ga)
                    if note:
                        try:
                            self.events.append({
                                'time': self.time, 'period': self.period,
                                'team': team.team_name, 'player': pl,
                                'event': 'MeshNote', 'note': note})
                        except Exception:
                            pass
        except Exception:
            pass

    def _process_gameplay_injuries(self):
        """Process potential injuries from gameplay.

        Grounded rate (W4, injury_data.QUICK_ENGINE_GENERAL_RATE): 0.31 per
        team per game -- Rotowire 2024-25 (819 injuries / 32 teams / 82
        games). The quick engines have no hit-injury path, so the general
        roll carries the full load. Victim/severity via the shared decision.
        """
        import random
        try:
            import injury_data as _inj
            _rate = _inj.QUICK_ENGINE_GENERAL_RATE
        except Exception:
            _rate = 0.31

        # One roll per team per game -> ~0.31 injuries per team-game.
        # Pick an injury victim from either team's healthy skaters
        victims = []
        for team in [self.home_team, self.away_team]:
            if random.random() > _rate:
                continue
            v = roll_game_injury(team)
            if v is not None:
                victims.append((team, v))

        for team, injured in victims:
            # Log the injury event
            self.events.append({
                'time': self.time,
                'period': self.period,
                'team': team.team_name,
                'player': injured,
                'event': 'Injury',
                'details': f'{injured.injury_type} ({injured.games_remaining_injured} games)'
            })

            print(f"🏥 Injury: {injured.first_name} {injured.last_name} - {injured.injury_type} ({injured.games_remaining_injured} games)")

    def _credit_assists(self, shooter, team_name):
        """Credit primary/secondary assists for a goal.

        Primary goes to the last successful passer to the shooter
        (tracked as assist_potential when passes complete); when no
        mechanical passer was tracked, the setup man is SELECTED by the
        shared decision (playmaking x dynamics) -- the same call GameSim
        makes. Secondary is attribute-weighted, not a dice roll.
        Returns (assist_ids, assist_players).
        """
        assist_ids, assist_players = [], []
        team = self.home_team if team_name == self.home_team.team_name else self.away_team
        by_id = {p.id: p for p in getattr(team, 'roster', [])}
        on_ice = self.on_ice.get(team_name, {})
        _skaters = [p for p in (on_ice.get('Forwards', []) + on_ice.get('Defense', []))
                    if p is not None]

        primary_id = getattr(shooter, 'assist_potential', None)
        if primary_id and primary_id != shooter.id and primary_id in by_id:
            assist_ids.append(primary_id)
            assist_players.append(by_id[primary_id])
            st = self.stats[team_name].get(primary_id)
            if st is not None:
                st['assists'] = st.get('assists', 0) + 1
            # Part B: ledger the pair for line-combination analytics.
            try:
                from mesh_system import record_assist_pair as _rap2
                _rap2(self.assist_pairs, by_id[primary_id], shooter,
                      team_name)
            except Exception:
                pass
        # Never carry a stale passer into the next goal
        try:
            shooter.assist_potential = None
        except Exception:
            pass

        # Part B: no mechanical passer tracked (the shooter carried it in
        # himself) -- select the setup man by the ONE shared decision:
        # playmaking attributes x relationship closeness with the shooter
        # x line chemistry. Most real goals come off a pass; this keeps
        # the primary rate unified with GameSim's reworked pass play, and
        # the ledger keeps the pair.
        # Tuned 2026-09-30 (scoring calibration): 0.60 -> 0.65. The sim
        # ledger was producing A/G 1.49-1.53, just under the 1.55-1.70
        # band; +0.05 primary lifts A/G into the band without touching
        # finishing constants.
        #
        # WS2 parity: the setup-man SELECTION is the ONE shared decision
        # (mesh_system.select_setup_man -- GameSim's playmaking_score path
        # is canonical). The per-engine rate gate (0.65 here vs 0.75 on
        # GameSim) is calibration for different mechanical-passer
        # frequencies, not the decision; the decision never has a copy.
        if not assist_ids:
            _pool = [p for p in _skaters if p.id != shooter.id]
            if _pool and random.random() < 0.65:
                _passer = None
                try:
                    from mesh_system import select_setup_man as _ssm4
                    _iso4 = bool(getattr(self, "is_playoff", False))
                    _passer = _ssm4(_pool, shooter, team, is_playoff=_iso4)
                except Exception:
                    _passer = None
                if _passer is not None:
                    assist_ids.append(_passer.id)
                    assist_players.append(_passer)
                    st = self.stats[team_name].get(_passer.id)
                    if st is not None:
                        st['assists'] = st.get('assists', 0) + 1
                    try:
                        from mesh_system import record_assist_pair as _rap3
                        _rap3(self.assist_pairs, _passer, shooter, team_name)
                    except Exception:
                        pass

        # Secondary assist: another on-ice teammate. WS2 parity: the SAME
        # decision GameSim makes -- tuned rate with the trait bonus applied
        # once and capped, selection via shared assist_weight x trait
        # bonus. Attribute-weighted, not a dice roll; the hierarchy
        # (attributes first) is unchanged, only the rate.
        from player_traits import get_sim_bonus as _tb3
        _sec_chance = 0.78
        for p in _skaters:
            if p.id not in (shooter.id, *assist_ids):
                try:
                    _sec_chance *= _tb3(p, "assist_chance_mult")
                except Exception:
                    pass
                break  # Only apply once (highest bonus)
        if random.random() < min(0.92, _sec_chance):
            candidates = [p for p in _skaters
                          if p.id not in (shooter.id, *assist_ids)]
            if candidates:
                try:
                    from mesh_system import assist_weight as _aw3
                    _iso3 = bool(getattr(self, "is_playoff", False))
                    _w3 = [max(0.05, _aw3(p, shooter, team,
                                           is_playoff=_iso3)
                               * _tb3(p, "assist_chance_mult"))
                           for p in candidates]
                    second = random.choices(candidates, weights=_w3, k=1)[0]
                except Exception:
                    second = random.choice(candidates)
                assist_ids.append(second.id)
                assist_players.append(second)
                st = self.stats[team_name].get(second.id)
                if st is not None:
                    st['assists'] = st.get('assists', 0) + 1
        return assist_ids, assist_players

    def _apply_chance_grade(self, shot_chance, shooter, goalie, shot_type,
                            puck_team_name, opp_team_name, contest_mult,
                            screened_now, shooters, shot_tool=None):
        """Chance grading (2026-09-28, per Muck): grade the scoring chance
        A/B/C at creation time via the shared mesh_system roll, then apply
        the grade finish multiplier and grade-specific clamp. Replaces the
        old flat [0.04, 0.16] clamp -- grade B keeps that band, grade A
        reaches NHL high-danger (~20%+), grade C is suppressed.

        (2026-10-01, per Muck): the clamp is PERSONAL -- the shooter's
        finishing scales his ceiling WITHIN the protected league envelope
        (mesh_system.personal_grade_ceiling, the same shared decision
        GameSim applies). The flat 0.18 grade-A ceiling for everyone is
        retired. shot_tool is the per-attempt shot-type value selected in
        _resolve_shot_event.

        The grade is stashed on self._last_chance_grade for the analytics
        recording below (per-player grade_a/b/c_shots + _goals). Never
        raises -- falls back to the flat clamp."""
        _grade = "B"
        try:
            from game_classes import PlayerPosition as _PPg
            from mesh_system import (roll_chance_grade as _rcg,
                                     chance_grade_finish_mult as _cgfm,
                                     chance_grade_clamp as _cgc)
            # -- location from shot type / position --------------------
            _spos = getattr(shooter, "primary_position", None)
            _is_d = _spos in (_PPg.DEFENSE, _PPg.LEFT_DEFENSE,
                              _PPg.RIGHT_DEFENSE)
            if getattr(self, "_is_breakaway", False):
                _loc = "breakaway"
            elif shot_type in ("tip", "deflection"):
                _loc = "netfront"
            elif _is_d and shot_type in ("slap shot", "one-timer"):
                # Classification fix (2026-09-30, workstream C2, Muck):
                # a defenseman's one-timer comes from the point -- it
                # used to fall through to "slot" (slot priors + the
                # slot+QR+clean grade-A hard gate), which GameSim never
                # did (location-based). Now parity: point is point.
                _loc = "point"
            else:
                _loc = "slot"
            # -- contest 0 (clean) .. 1 (smothered) from the mult -------
            # Observed mult range is ~0.90-0.95 (never near 1.0); map
            # relative to that band, not the theoretical 0.90-1.00.
            try:
                _contest01 = max(0.0, min(1.0,
                                          (0.95 - float(contest_mult)) / 0.05))
            except Exception:
                _contest01 = 0.5
            # -- defending D pair + their fatigue -----------------------
            _def_team = (self.away_team
                         if puck_team_name == self.home_team.team_name
                         else self.home_team)
            try:
                _d_onice = (self.on_ice.get(_def_team.team_name, {})
                            or {}).get("Defense", [])
                _defenders = [d for d in _d_onice if d]
            except Exception:
                _defenders = []
            try:
                _dfats = [self.stats[_def_team.team_name].get(d.id, {})
                          .get('fatigue', 0) for d in _defenders]
                _d_fatigue = (sum(_dfats) / len(_dfats)) if _dfats else 50.0
            except Exception:
                _d_fatigue = 50.0
            # -- team defensive weakness (GA/GP vs ~3.0 par) ------------
            _team_d_weak = 1.0
            try:
                _ga = float(getattr(_def_team, "goals_against", 0) or 0)
                _gp = float(getattr(_def_team, "games_played", 0) or 0)
                if _gp > 5 and _ga > 0:
                    _gpg = _ga / _gp
                    _team_d_weak = max(0.85, min(1.30, _gpg / 3.0))
            except Exception:
                pass
            # -- gametime: rivalry / morale / clutch / crowd ------------
            _rivalry_heat = 0.0
            try:
                _lg = getattr(self, "league", None)
                _rivs = getattr(_lg, "rivalries", None) if _lg else None
                if _rivs:
                    import reputation_system as _rs
                    _shooting_team = (self.home_team
                                      if puck_team_name ==
                                      self.home_team.team_name
                                      else self.away_team)
                    _rh = _rs.get_rivalry_heat(_rivs, _shooting_team,
                                               _def_team)
                    _rivalry_heat = float(_rh.get("heat", 0) or 0)
            except Exception:
                pass
            try:
                _morale = float(getattr(shooter, "morale", 70) or 70)
            except Exception:
                _morale = 70.0
            try:
                _sdiff = abs(self.score.get(puck_team_name, 0)
                             - self.score.get(opp_team_name, 0))
                _per = int(getattr(self, "period", 1) or 1)
                _t = float(getattr(self, "time", 0) or 0)
                # clutch: OT, or 3rd period under 5:00 within a goal
                _clutch = (_per >= 4) or (_per == 3 and _sdiff <= 1
                                         and _t >= 3300)
            except Exception:
                _clutch = False
            try:
                _is_home = puck_team_name == self.home_team.team_name
                _cm = (self._crowd_home_mult if _is_home
                       else self._crowd_away_mult)
                _crowd_edge = max(-1.0, min(1.0, (float(_cm) - 1.0) * 15.0))
            except Exception:
                _crowd_edge = 0.0
            # -- schemed-against superstars (2026-09-30, Muck) ----------
            # AS a scenario battle (scenario_composites.schemed_factor_for_
            # shooter): the defending TEAM shades an elite/generational
            # threat — his grade-A looks tighten, his linemates skate into
            # the freed ice. One factor per chance, never stacked. One
            # decision, two fidelities (GameSim calls the same helper).
            try:
                from scenario_composites import (schemed_factor_for_shooter
                                                 as _sffs)
                _d_unit = [d for d in _defenders]
                try:
                    _d_fwds = ((self.on_ice.get(_def_team.team_name, {})
                                or {}).get("Forwards", []))
                    _d_unit += [f for f in _d_fwds if f]
                except Exception:
                    pass
                _schemed_f = _sffs(shooter, shooters, _d_unit, _loc,
                                   sim=self, off_team=puck_team_name,
                                   def_team=opp_team_name)
            except Exception:
                _schemed_f = 1.0
            # -- 6v5 scramble tilt (workstream B, 2026-09-30) -------------
            # Generation side only: the six-man unit's net-front chaos
            # (attribute-vs-attribute vs the defense's box-out) tilts WHO
            # earns grade A. Finishing constants/clamps untouched.
            _tilt65 = 1.0
            try:
                if puck_team_name in getattr(self, "goalie_pulled", set()):
                    from six_on_five import grade_tilt_ctx as _gtc65q
                    _a_onice = self.on_ice.get(puck_team_name, {}) or {}
                    _a_unit = [p for p in (_a_onice.get("Forwards", [])
                                           + _a_onice.get("Defense", []))
                               if p is not None]
                    _tilt65 = _gtc65q(_a_unit, _d_unit
                                      ).get("six_on_five_tilt", 1.0)
            except Exception:
                pass
            # -- 3v3 open-ice tilt (workstream B(e), 2026-09-30) -----------
            # Generation side only: 3v3 OT's open ice tilts grade-A earning
            # by the on-ice units' skating/chance-creation. The live lever
            # for (e), alongside the 1.60x volume above.
            _tilt3v3 = 1.0
            try:
                if getattr(self, "_ot_3v3", False):
                    from six_on_five import ot_open_ice_tilt as _ot33q
                    _a_onice3 = self.on_ice.get(puck_team_name, {}) or {}
                    _a_unit3 = [p for p in (_a_onice3.get("Forwards", [])
                                            + _a_onice3.get("Defense", []))
                                if p is not None]
                    _tilt3v3 = _ot33q(_a_unit3, _d_unit)
            except Exception:
                pass
            # -- roll ---------------------------------------------------
            _ctxq = {}
            _grade = _rcg(
                _loc, _contest01, shooter,
                defenders=_defenders, goalie=goalie,
                situation={
                    "quick_release": shot_type == "one-timer",
                    "screened_goalie": bool(screened_now),
                    "won_spot": False,
                    # D12 (2026-09-30): quick_sim DOES generate a discrete
                    # rebound event now -- _resolve_rebound_event, fired off
                    # real saves in _resolve_shot_event. It is the fast
                    # approximation of GameSim._resolve_rebound_chance:
                    # the same rebound-control trigger ladder, the same
                    # anticipation+offensive_awareness finisher pick, and
                    # the SHARED mesh_system.netfront_finish_chance
                    # decision (never a different formula). The graded
                    # stream itself never emits rebound situations, so
                    # this stays False; roll_chance_grade hard-gates any
                    # rebound situation to grade A regardless.
                    "rebound": False,
                    "tip": shot_type in ("tip", "deflection"),
                },
                game_ctx={
                    "rivalry_heat": _rivalry_heat,
                    "morale": _morale,
                    "clutch": _clutch,
                    "crowd_edge": _crowd_edge,
                    "is_playoff": bool(getattr(self, "is_playoff", False)),
                    "d_fatigue": _d_fatigue,
                    "team_d_weakness": _team_d_weak,
                    "six_on_five_tilt": _tilt65,
                    "ot_3v3_tilt": _tilt3v3,
                },
                context_out=_ctxq)
            shot_chance = shot_chance * _cgfm(_grade)
            # Schemed-against factor (scenario battle): applied to the
            # grade-A chance, never to finishing. Multiplicative, bounded.
            try:
                if _schemed_f != 1.0:
                    shot_chance *= _schemed_f
            except Exception:
                pass
            # Line chemistry (2026-09-30, Muck): the shared unit-efficiency
            # multiplier — archetype fit, composite complementarity,
            # talent+performance foundation, morale/bonds. Situation-aware
            # (EV line balance / PP formation completeness / PK scheme),
            # bounded per-line, truthful (no league pin). One decision,
            # two fidelities — GameSim applies the same helper at the
            # same point. Never touches finishing or grade ceilings.
            try:
                from line_chemistry import (unit_efficiency as _lcef,
                                            pk_denial_factor as _lkdf,
                                            detect_situation as _lcdet)
                _sit_lc = _lcdet(sim=self, team=puck_team_name)
                _lc_eff = _lcef(shooters, situation=_sit_lc, sim=self,
                                team=puck_team_name)
                if _lc_eff != 1.0:
                    shot_chance *= _lc_eff
            except Exception:
                _lc_eff = 1.0
            # STACKING (2026-09-30, workstream C, Muck): the opportunity
            # amplifiers on one chance — grade boost, schemed relief,
            # chemistry — combine sub-multiplicatively (strongest keeps
            # full value, further boosts keep 30% of their excess), not
            # freely multiplicative. Denials (PK denial, defensive
            # contest) are applied separately and keep full
            # multiplicative power — honest brakes, never muted.
            try:
                from scenario_composites import (
                    combine_stacked_amplifiers as _csa)
                _gm = _cgfm(_grade)
                _free = _gm * _schemed_f * _lc_eff
                if _free != 0.0:
                    shot_chance *= _csa(_gm, _schemed_f, _lc_eff) / _free
            except Exception:
                pass
            try:
                # defending PK unit's denial applies when the attack is on
                # the PP ("pp"), not when the attack is shorthanded.
                if _sit_lc == "pp":
                    _deny = _lkdf(_d_unit, sim=self, team=opp_team_name)
                    if _deny != 1.0:
                        shot_chance *= _deny
            except Exception:
                pass
            # Breakaway scenario (§6): on a clean breakaway, the battle is
            # shooter (skating/finishing/chance_creation) vs goalie alone.
            # No overlapping single-composite hooks here — clean add.
            try:
                if _loc == "breakaway":
                    from scenario_composites import apply_scenario as _asc_qb
                    shot_chance = _asc_qb(shot_chance, [shooter], [goalie],
                                          "breakaway", sim=self,
                                          off_team=puck_team_name,
                                          def_team=opp_team_name)
            except Exception:
                pass
            # Team clutch (team_clutch.py): in clutch moments, big-game
            # rosters elevate and fragile rooms shrink. Same shared helper
            # the lightweight uses -- parity by construction. Cached per
            # team per game (heat is per-matchup, constant within a game).
            # (Resolve the shooting team here: the _shooting_team above is
            # only set when the league has rivalry data.)
            if _clutch:
                try:
                    from team_clutch import team_clutch_factor as _tcf
                    _cc = getattr(self, "_team_clutch_cache", None)
                    if _cc is None:
                        _cc = self._team_clutch_cache = {}
                    _cs = (self.home_team
                           if puck_team_name == self.home_team.team_name
                           else self.away_team)
                    _ck = _cs.team_name
                    _cf = _cc.get(_ck)
                    if _cf is None:
                        _cf = _cc[_ck] = _tcf(
                            _cs,
                            league=getattr(self, "league", None),
                            matchup_heat=_rivalry_heat)
                    shot_chance *= _cf
                except Exception:
                    pass
            _lo, _hi = _cgc(_grade)
            # Personal finishing ceiling (2026-10-01, Muck): the
            # shooter's finishing scales his grade ceiling WITHIN the
            # protected league envelope -- the same shared decision
            # GameSim applies. Scenario lift (heat, linemates, chemistry,
            # scheme relief) creates windows for breakouts; stars stay at
            # the envelope max. League max unchanged; the flat grade-A
            # 0.18 for everyone is retired.
            try:
                from mesh_system import personal_grade_ceiling as _pgc
                from mesh_system import ceiling_scenario_mult as _csm
                _mates = None
                try:
                    _oi = self.on_ice.get(puck_team_name, {})
                    _mates = _oi.get('Forwards', None)
                except Exception:
                    pass
                _sm = _csm(shooter, linemates=_mates)
                _lo, _hi = _pgc(shooter, _grade, shot_tool=shot_tool,
                                scenario_mult=_sm)
            except Exception:
                pass
            shot_chance = max(_lo, min(_hi, shot_chance))
        except Exception:
            shot_chance = max(0.04, min(0.16, shot_chance))
            _grade = "B"
        self._last_chance_grade = _grade
        # Analytics integration (2026-10-01): stash the scenario/
        # composite context that drove this grade -- recorded on the
        # lightweight shot log. Additive; never affects the grade.
        try:
            self._last_chance_context = dict(_ctxq)
        except Exception:
            pass
        return shot_chance

    def _resolve_shot_event(self, shooter, goalie, puck_team_name, opp_team_name, fatigue_factor, pressure_modifier, position_factor, shooters,
                            sh_rush_sus=None):
        """Enhanced shot resolution using multiple attributes"""
        # Determine shot type based on position and situation
        wristshot_val = getattr(shooter, 'wristshot', 10)
        slapshot_val = getattr(shooter, 'slapshot', 10)
        one_timer_val = getattr(shooter, 'one_timer', 10)
        backhand_val = getattr(shooter, 'backhand', 10)
        
        # Choose shot type
        # Sniper one-timers at EV (2026-09-30, (c) winger spotlight, Muck):
        # the one_timer attribute was PP-only for forwards — a sniper's
        # signature weapon didn't exist at even strength. Attribute-driven:
        # better one-timer tool = more one-timer looks (feeds find him).
        # Bounded and modest; the d_to_d_onetimer scenario resolves them.
        _ot_prob = max(0.0, min(0.20, (float(one_timer_val) - 60.0) / 200.0))
        # Spotlight talent gate (2026-09-30, workstream C, Muck): who
        # EARNS the one-timer volume -- elite trigger + awareness +
        # finishing ~1.0, average ~0.4, below-average ~0.15. The looks
        # concentrate on the shooters, never a participation trophy.
        # Archetype factor (C2): the one-timer is a sniper's signature --
        # role players get their looks elsewhere.
        # (PP one-timer rate is the tuning crew's lane -- untouched.)
        try:
            from scenario_composites import (
                onetimer_talent_gate as _otg,
                onetimer_archetype_factor as _oaf)
            _ot_prob *= _otg(shooter) * _oaf(shooter)
        except Exception:
            pass
        if self.pp_team and random.random() < 0.3:  # More one-timers on PP
            shooting_base = one_timer_val
            shot_type = "one-timer"
        elif (not self.pp_team and random.random() < _ot_prob
              and shooter.primary_position in [
                  PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING,
                  PlayerPosition.CENTER]):
            shooting_base = one_timer_val
            shot_type = "one-timer"
        elif shooter.primary_position in [PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]:
            if random.random() < 0.7:
                shooting_base = wristshot_val
                shot_type = "wrist shot"
            else:
                shooting_base = backhand_val
                shot_type = "backhand"
        elif shooter.primary_position == PlayerPosition.CENTER:
            shooting_base = wristshot_val * 0.6 + one_timer_val * 0.4
            shot_type = "wrist shot"
        else:  # Defense
            shooting_base = slapshot_val
            shot_type = "slap shot"
            
        # Shooter skill: the ONE shared finishing decision (2026-10-01,
        # per Muck: CONSOLIDATE) -- mesh_system.finishing_rating, the
        # diverse 13-member harmonic blend both engines read. The
        # shot-type/position selection above is this engine's own texture;
        # the blend is the shared decision.
        # Fatigue is a VOLUME channel (unified decision, divergence #7):
        # tired legs shoot less often; they don't finish worse per shot.
        # Conversion-side fatigue lives in the impact tier below.
        from mesh_system import shooter_skill_composite as _ssc
        shooter_skill = _ssc(shooter, shooting_base)

        # Situational goalie (2026-09-28, per Muck): the situation
        # re-weights the goalie composite (screened -> positioning+composure,
        # tip -> reflexes, breakaway -> reflexes+composure, point -> 
        # positioning+rebound control).
        _situation = "clean"
        try:
            _screens0 = getattr(self, "_active_screens", {}) or {}
            if puck_team_name in _screens0:
                _situation = "screened"
            elif shot_type in ("tip", "deflection"):
                _situation = "tip"
            elif getattr(self, "_is_breakaway", False):
                _situation = "breakaway"
            else:
                from game_classes import PlayerPosition as _PP2
                _spos = getattr(shooter, "primary_position", None)
                if (_spos in (_PP2.DEFENSE, _PP2.LEFT_DEFENSE, _PP2.RIGHT_DEFENSE)
                        and shot_type == "slap shot"):
                    _situation = "point"
        except Exception:
            pass

        # Enhanced goalie attributes
        goalie_skill = self._calculate_goalie_save_skill(goalie, shot_type, situation=_situation) if goalie else 8
        # Goaltending parity (mesh_system.effective_goalie_skill): compress
        # the raw 1-100 composite toward the measured starter mean (92.6)
        # before the differential -- a 98 goalie deciding games outright is
        # a parity failure. Skaters decide games. The raw composite is
        # untouched for UI/AI; this only affects the conversion formula.
        try:
            from mesh_system import effective_goalie_skill as _egs
            goalie_skill = _egs(goalie_skill)
        except Exception:
            pass
        
        # NHL-realistic shooting percentage: ~9% base
        # Each point of skill difference shifts scoring chance ~0.3-0.4%
        # (piecewise talent sensitivity -- see mesh_system).
        # Recalibrated (mesh_system): both skills resolve on the 1-100 scale
        # with goalies systematically ~15 points above shooters, so the raw
        # differential is recentered to restore the designed 9% for an
        # average shot. Talent sensitivity itself is unchanged.
        from mesh_system import recalibrated_shot_chance
        skill_diff = shooter_skill - goalie_skill
        shot_chance = recalibrated_shot_chance(skill_diff)
        # Truthful-block compensation (2026-09-29, per Muck): the shared
        # block decision now stops ~8% of attempts (was a flat 5% gate),
        # and a blocked shot never reaches the goal roll. The "designed
        # 9%" was P(goal|attempt) under the old 5% regime; to preserve it,
        # the unblocked conversion scales by (1-0.05)/(1-0.08) ~= 1.03.
        # Scoring volume is thus held constant while the block rate
        # becomes attribute-driven and truthful in structure.
        shot_chance *= 1.03
        # --- attribute composites (additive, bounded) ---
        # Finishing vs goalie-save: the same decision GameSim applies --
        # the shooter's finishing toolkit against the goalie's broad save
        # toolkit. Scoring-sensitive rails [0.97, 1.03] on both sides (the
        # goalie side is inverted: a better save composite lowers the goal
        # chance). One decision, two fidelities.
        # Winger spotlight (2026-09-30, (c) Muck): on one-timer shots the
        # d_to_d_onetimer scenario battle REPLACES these single-composite
        # hooks (§6 rule 2 — never stack; the scenario already contains
        # finishing and goalie_save). EV only: PP conversion is the
        # tuning crew's lane. (QS tips/deflections resolve on their own
        # attribute-rich deflection path — deflections/off_the_puck/
        # balance vs the goalie — left untouched.)
        _qs_ev = self.pp_team is None
        _qs_ot = (_qs_ev and shot_type == "one-timer"
                  and goalie is not None)
        try:
            if _qs_ot:
                from scenario_composites import apply_scenario as _asc_qsot
                shot_chance = _asc_qsot(shot_chance, [shooter], [goalie],
                                        "d_to_d_onetimer", sim=self,
                                        off_team=puck_team_name,
                                        def_team=opp_team_name)
                # Point-shot feeder gate (2026-09-30, workstream C2,
                # Muck): the play design feeds the look, the SHOOTER's
                # own shooting tools + hockey IQ decide what it becomes.
                # Smooth 0.85..1.0 -- mediocre shooters don't mint goals
                # off play design alone.
                try:
                    from scenario_composites import (
                        point_shot_talent_gate as _pstg)
                    shot_chance *= _pstg(shooter)
                except Exception:
                    pass
            else:
                from attribute_composites import apply_amplifier as _ac_qs
                shot_chance = _ac_qs(shot_chance, shooter, "finishing", sim=self,
                                     team=puck_team_name, energy=fatigue_factor * 100)
                if goalie:
                    shot_chance = _ac_qs(shot_chance, goalie, "goalie_save",
                                        sim=self, team=opp_team_name, invert=True)
        except Exception:
            pass
        # Heater shutdown REMOVED (2026-09-29, per Muck): the damper below cut
        # a hot player's finishing up to -50% when mesh_form heat > 0.60.
        # That fought the seize-the-moment vision -- a heater should feel
        # MORE dangerous, not get quietly nerfed. Heater self-correction
        # lives in the grade system where it belongs: heat boosts chance
        # earning (CHANCE_HEAT_BOOST swagger) and draws tighter checking
        # (CHANCE_HEAT_CHECK) -- the league adjusts, the player stays
        # dangerous. No caps, no dampers, no "impossible" outcomes.

        # Defensive contest 2026-09-28 (shared decision): the two on-ice
        # defenders contest every shot -- blocks (shot_blocking), gap
        # (defensive_awareness), angles (positioning), sticks (pokecheck).
        # Modest per-shot effect (NHL block rates are real but not dominant).
        _contest = 1.0
        try:
            from mesh_system import defensive_contest_mult as _dcm
            _def_team = (self.away_team if puck_team_name == self.home_team.team_name
                         else self.home_team)
            _d_onice = (self.on_ice.get(_def_team.team_name, {}) or {}).get("Defense", [])
            _contest = _dcm([d for d in _d_onice if d])
            if _contest != 1.0:
                shot_chance *= _contest
        except Exception:
            pass

        # Net-front screen 2026-09-28 (shared decision): a set screen
        # degrades the GOALIE's sightline (goalie-side penalty), not a
        # shooter bonus. Consumed by this shot.
        _screened_now = False
        try:
            from mesh_system import screen_goalie_mult as _sgm
            _screens = getattr(self, "_active_screens", {}) or {}
            _screener = _screens.pop(puck_team_name, None)
            if _screener is not None:
                _screened_now = True
                _sp = _sgm(_screener, goalie)
                if _sp != 1.0:
                    # Goalie sees it late: effective skill drops
                    goalie_skill = goalie_skill * _sp
                    skill_diff = shooter_skill - goalie_skill
                    shot_chance = recalibrated_shot_chance(skill_diff)
                    shot_chance *= 1.03  # truthful-block compensation (see above)
                    shot_chance *= _contest  # re-apply contest on new base
        except Exception:
            pass

        # Superstar tune 2026-09-28 (shared decisions): D point-shot
        # conversion discount (point shots through traffic convert at
        # ~55% of forward rate) and sniper archetype finishing tilt
        # (5-10% edge for pure snipers). Both engines apply these.
        try:
            from mesh_system import (defense_point_shot_discount as _dpsd,
                                     archetype_finish_tilt as _aft)
            shot_chance *= _dpsd(shooter) * _aft(shooter)
        except Exception:
            pass

        # Parity engine on CONVERSION (divergence #8, unified channel):
        # GameSim applies pregame_multiplier on shot quality; this engine
        # applies the same shared decision here on shot_chance.
        try:
            _pm = self._parity_matchup or {}
            _ph = (puck_team_name == self.home_team.team_name)
            shot_chance *= _pm.get("home" if _ph else "away", 1.0)
        except Exception:
            pass

        # -- Scoring-balance tune (additive): the shared BASE_SAVE_TUNE both
        # engines apply ("slight" SV% nudge toward .900), plus tie-game late
        # tightening ("protect the point": tied in the 3rd under 10:00 left,
        # both teams trade chances for structure). Same shared decisions as
        # GameSim (scoring_balance); this engine applies them on shot_chance.
        # Own channel, never overrides the agreed math above.
        try:
            import scoring_balance as _sbal
            _tune = float(_sbal.BASE_SAVE_TUNE)
            if _tune != 1.0:
                shot_chance *= _tune
            _secs_left = 3600.0 - float(getattr(self, "time", 0) or 0)
            _tlf = _sbal.tie_late_factor(
                int(getattr(self, "period", 1) or 1), _secs_left,
                self.score.get(self.home_team.team_name, 0),
                self.score.get(self.away_team.team_name, 0))
            if _tlf != 1.0:
                shot_chance = min(0.45, max(0.005, shot_chance * _tlf))
        except Exception:
            pass

        # -- Impact tier (additive): tired / normal / big shot. Scales the
        # existing shot_chance on top of the agreed math above -- big shots
        # finish cleaner, tired ones are easier stops. Never overrides it.
        try:
            import impact_system as _imp
            _sd = self.score.get(puck_team_name, 0) - self.score.get(opp_team_name, 0)
            _ictx = _imp.ImpactContext(
                fatigue=max(0.0, min(100.0, fatigue_factor * 100.0)),
                on_pk=(self.pk_team == puck_team_name),
                on_pp=bool(self.pp_team),
                score_diff=int(_sd),
                period=int(getattr(self, "period", 1) or 1),
                clock_seconds=max(0.0, 3600.0 - float(getattr(self, "time", 0) or 0)),
                is_playoff=bool(getattr(self, "is_playoff", False)),
                crowd_energy=float(getattr(self, "_crowd_energy", 50.0) or 50.0),
                crowd_mood=float(getattr(self, "_crowd_mood_home", 0.0) or 0.0)
                    if puck_team_name == self.home_team.team_name
                    else -float(getattr(self, "_crowd_mood_home", 0.0) or 0.0),
            )
            _seff = _imp.shot_effects(_imp.classify_shot_impact(shooter, _ictx))
            _sm = _seff["save_prob_mult"]
            if _sm != 1.0:
                shot_chance = min(0.45, max(0.005, shot_chance / _sm))
        except Exception:
            pass

        # -- Perfect mesh (additive): situational alignment -- chemistry,
        # system fit, morale, form -- pays a super-additive kicker with an
        # underdog tilt, plus playoff elevators in April. Multiplies the
        # agreed math above; never overrides it.
        try:
            from mesh_system import mesh_factor as _mesh_factor
            _shooting_team = (self.home_team if puck_team_name == self.home_team.team_name
                              else self.away_team)
            _mates = [p for p in shooters if p is not shooter]
            _mf = _mesh_factor(shooter, _mates, _shooting_team,
                               is_playoff=bool(getattr(self, "is_playoff", False)))
            if _mf != 1.0:
                shot_chance = min(0.45, max(0.005, shot_chance * _mf))
        except Exception:
            pass
        
        # Team tactics affect shot quality
        # Get the shooting team's tactics
        shooting_team = self.home_team if puck_team_name == self.home_team.team_name else self.away_team
        defending_team = self.away_team if puck_team_name == self.home_team.team_name else self.home_team

        # -- Goalie personality (additive): temperament x traffic, coach
        # trust, room fit, youth tax, playoff elevator. Same shared math as
        # GameSim (goalie_personality.py) so the engines stay converged;
        # applied as a save-side divisor like the impact-tier hook above.
        # Point shots (slap shot) go through traffic; one-timers catch the
        # goalie moving laterally -- both count as traffic looks here.
        try:
            import goalie_personality as _agp
            try:
                _gcoach = getattr(defending_team, "head_coach",
                                  getattr(defending_team, "coach", None))
            except Exception:
                _gcoach = None
            try:
                _gcgp = int(getattr(getattr(goalie, "stats", None),
                                    "career_games", 0) or 0)
            except Exception:
                _gcgp = 0
            _gplayoff = bool(getattr(self, "is_playoff", False))
            _gmult = _agp.goalie_mesh_factor(
                goalie, team=defending_team, coach=_gcoach,
                is_playoff=False, career_gp=_gcgp)
            # Real per-game state (divergence #10): bounce-back, tilt and
            # off-night now fire here exactly as in GameSim -- no more
            # state=None. Same shared goalie_personality decisions.
            _gst = None
            try:
                if goalie is not None:
                    _gst = self.goalie_personality_state.get(goalie.id)
                    if _gst is None:
                        _gst = _agp.new_game_state()
                        self.goalie_personality_state[goalie.id] = _gst
            except Exception:
                _gst = None
            _gmult *= _agp.save_prob_mult(
                goalie,
                {"traffic": shot_type in ("slap shot", "one-timer"),
                 "soft": False},
                state=_gst, is_playoff=_gplayoff, career_gp=_gcgp)
            if _gmult != 1.0:
                shot_chance = min(0.45, max(0.005, shot_chance / _gmult))
        except Exception:
            pass
        
        # Legacy slider blocks retired: tactic_power_play /
        # tactic_penalty_kill / tactic_even_strength now fold into
        # resolve_team_tactics itself, and the _systems_edge_for channel
        # below (plus the shot_qual channel) applies them -- one channel,
        # no double-counting with the installed modules.
        
        # Home-ice + crowd (arena_atmosphere): the structural last-change
        # edge (+0.25% flat) plus the building's mood -- a jacked crowd lifts
        # the home side, a nervous/toxic one drags it; young visitors get
        # rattled in loud hostile barns. Circumstantial, averages about the
        # old flat +0.5%, but it can now go the other way.
        if puck_team_name == self.home_team.team_name:
            shot_chance += 0.0025
            shot_chance *= self._crowd_home_mult
        else:
            shot_chance *= self._crowd_away_mult
        
        # Clamp to realistic NHL range (5% - 15%)
        shot_chance = max(0.05, min(0.15, shot_chance))

        # FM team-talk / morale boost (set via set_team_talk_boost)
        shot_chance *= self.team_boost.get(puck_team_name, 1.0)

        # Dressing-room talks (module 03): pre-game and intermission words
        # move finishing a touch. Own channel, capped +/-4%.
        shot_chance *= self.dressing_boost.get(puck_team_name, 1.0)

        # Situations channel: the room, the bench, and the kids move
        # finishing a few percent either way. Own channel, like the
        # controversy momentum channel -- not part of any capped budget.
        shot_chance *= self._situation_edge_for(puck_team_name)
        # Installed NHL systems: your attack vs their structure, your
        # power play vs their kill. Own channel, precomputed per game.
        shot_chance *= self._systems_edge_for(puck_team_name)
        # O-zone system sets chance quality: cycle teams get better looks,
        # rush teams get more looks. Own channel, precomputed per game.
        # The quick-sim has no per-tick clamp to absorb SHOT_LIFT (unlike
        # GameSim's [0.2, 0.85] gate), so the full lift flows into volume --
        # dilute by the full SHOT_LIFT here to keep scoring flat while
        # volume rises to real NHL levels. Team differentiation survives
        # via shot_vol (undiluted) and the qual/vol tradeoff.
        try:
            _m = self._systems_matchup or {}
            _h = puck_team_name == self.home_team.team_name
            import tactics as _txq
            shot_chance *= _m.get("home_shot_qual" if _h else "away_shot_qual",
                                  1.0) / _txq.SHOT_LIFT
        except Exception:
            pass
        # Power-play finishing (parity fix 2026-09-30): the man advantage
        # converts better -- extra space, tired killers -- and it applies
        # BEFORE the grade clamp. GameSim applies its 2.2x man-advantage
        # factor on the xG path, i.e. before its per-step min(0.95, ...)
        # caps; quick-sim's 1.6x now lands before _apply_chance_grade's
        # 0.18 grade-A clamp so the clamp binds on PP chances too. One
        # decision, two fidelities -- the PP edge comes from chance
        # quality/volume, not from bypassing the quality ceiling.
        # (5v3's 3.0x has no quick-sim state to key off; accepted gap.)
        if getattr(self, "pp_team", None) == puck_team_name:
            shot_chance *= 1.6
        # WS4 H1 -- zone-entry quality (GameSim _determine_zone_entry_type,
        # simulation.py:3051, fast fidelity): a structured PP carries the
        # puck in with control (clean looks off the entry); a malformed
        # unit dumps it in and grinds (worse looks). The shared
        # pp_zone_sustenance differentiates the unit's entries --
        # conversion channel (the volume half already lives on the
        # event-type gate above). Bounded [0.875, 1.125]; additive.
        try:
            if getattr(self, "pp_team", None) == puck_team_name:
                _entry_q = 1.0 + 0.5 * (
                    self._pp_forecheck_sustenance() - 1.0)
                if _entry_q != 1.0:
                    shot_chance *= _entry_q
        except Exception:
            pass
        # WS4 H4 -- 5v4 rush defense (GameSim simulation.py:3173, fast
        # fidelity): the PP covers the ice with five, so the shorthanded
        # rush meets structure -- def_roll *= 1.0 + 0.42*(sus-0.68) on the
        # watched path. No defender roll exists in this engine's shot
        # resolution, so the same shape suppresses the chance directly
        # (direction-identical: better structure -> worse SH look).
        # Only on SH-rush chances (sh_rush_sus set by the strip-back
        # branch); every other caller is untouched.
        try:
            if (sh_rush_sus is not None
                    and getattr(self, "pp_team", None) is not None
                    and puck_team_name == getattr(self, "pk_team", None)):
                _rush_d = 1.0 + 0.42 * (float(sh_rush_sus) - 0.68)
                if _rush_d != 1.0 and _rush_d > 0:
                    shot_chance *= 1.0 / _rush_d
        except Exception:
            pass
        shot_chance = self._apply_chance_grade(
            shot_chance, shooter, goalie, shot_type, puck_team_name,
            opp_team_name, _contest, _screened_now, shooters,
            shot_tool=shooting_base)

        # 6-on-5 volume lives on the event-type gate above (divergence #13:
        # 2.2x, same as GameSim) -- not here on conversion.
        # EHM shift-fatigue: a unit out past ~40s degrades.
        shot_chance *= self._shift_fatigue_mult(puck_team_name)
        # Last change: the home coach got his matchup this shift.
        shot_chance *= self._matchup_edge.get(puck_team_name, 1.0)

        # Shot fate, block arm -- D11 (2026-09-30, Muck: CONSOLIDATE):
        # AdvGS's speed-optimized approximation of the ONE shared block
        # decision (approx_block_prob -- the same formula as
        # mesh_system.shot_block_prob; the unit's best blocker resolves
        # once per unit via _block_unit, not per shot). Location is the
        # nearest-spot proxy from the shooter's rink coordinates;
        # fatigue is the live shift-fatigue curve. sys/dz/pressure/
        # tactics are neutral -- AdvGS has no deployment-layer state
        # (documented fidelity gap, not a formula difference). A blocked
        # shot never reaches the goal roll. The miss arm (D11/RC1) rolls
        # BEFORE the goal roll below -- fate changes P(goal|attempt),
        # the same decision GameSim makes.
        _fate_missed = False
        _blocked_now = False
        _defender = None
        _plus_x = (puck_team_name == self.home_team.team_name)
        _qs_loc = qs_shot_location(getattr(shooter, "x", 100.0),
                                   getattr(shooter, "y", 42.5),
                                   attacking_plus_x=_plus_x)
        _qs_dist = qs_shot_distance(getattr(shooter, "x", 100.0),
                                    getattr(shooter, "y", 42.5),
                                    attacking_plus_x=_plus_x)
        try:
            _def_team = (self.away_team if puck_team_name == self.home_team.team_name
                         else self.home_team)
            _dtn = _def_team.team_name
            _was_blocked, _pdef, _p_block = approx_block_prob(
                shooter, self._block_unit(_dtn), location=_qs_loc,
                situation={"fatigue": self._shift_fatigue_mult(_dtn)})
            _blocked_now, _defender = _was_blocked, _pdef
            if _blocked_now:
                self.events.append({
                    'time': self.time, 'period': self.period,
                    'team': opp_team_name, 'player': _defender,
                    'event': 'Shot Blocked'})
        except Exception:
            _blocked_now = False
            _defender = None
        shot_blocked = bool(_blocked_now)
        
        # Position shooter and determine result
        shot_start = (shooter.x, shooter.y)
        duration = random.uniform(1.0, 1.7)
        
        # Empty net (divergence #4): GameSim's canonical zone-based
        # auto-goal -- 0.30 deep in the OZ, 0.10 neutral zone, 0.03 from
        # deep. Same 200-ft rink scale as GameSim (OZ > 125 attacking
        # +x for home, mirrored for away). The old flat 0.85-per-shot
        # made every empty-net shot nearly automatic; real (and GameSim)
        # empty-netters come from zone position, not shot volume.
        #
        # RC4 parity (2026-10-01): the shooter's shift coordinates are
        # static for the whole shift and don't reflect the turnover
        # reality of an EN chance -- GameSim's EN fires on a turnover,
        # usually in the pressing team's OZ (the shooting team's DZ).
        # Roll the zone from the turnover distribution instead of reading
        # stale coordinates. GameSim rolls per turnover; AdvGS rolls per
        # shot (rarer), so the mix is weighted toward higher-probability
        # zones to compensate: DZ 0.60 / NZ 0.30 / OZ-deep 0.10, expected
        # ~0.08 per EN shot, targeting ~0.08 EN/g (NHL strategic-pull
        # rate; the phantom delayed-penalty EN is fixed by RC2).
        _en_zone_roll = random.random()
        if _en_zone_roll < 0.60:
            _en_prob = 0.03
        elif _en_zone_roll < 0.90:
            _en_prob = 0.10
        else:
            _en_prob = 0.30
        _empty_net = (not shot_blocked
                      and opp_team_name in self.goalie_pulled
                      and random.random() < _en_prob)
        # D11 miss arm, RC1 parity (2026-10-01): the ONE shared miss
        # decision (mesh_system.shot_miss_prob), rolled BEFORE the goal
        # roll -- a miss is off-net and can never be a goal, the same
        # decision GameSim makes (simulation.py:5058, miss -> return
        # before _resolve_shot_on_goal). Grade-aware via _last_chance_grade
        # (set in _apply_chance_grade above); distance is AdvGS's
        # coordinate proxy for GameSim's location-based distance. Blocked
        # shots never reach here; empty-net shots skip the miss roll (the
        # EN auto-goal is its own decision, same as GameSim's
        # turnover-gated EN which never rolls a miss).
        _fate_missed = False
        if not shot_blocked and not _empty_net:
            try:
                from mesh_system import shot_miss_prob as _smp0
                _miss_grade0 = str(getattr(self, "_last_chance_grade", "B")
                                   or "B")
                _fate_missed = (random.random()
                                < _smp0(shooter, _miss_grade0, _qs_dist))
            except Exception:
                _fate_missed = False
        if shot_blocked:
            shot_result = 'BLOCKED'
        elif _fate_missed:
            # Off-net: no goal roll, no save. The attempt still counts as
            # a shot and records its grade below (xG backbone).
            shot_result = 'MISS'
            self.events.append({'time': self.time, 'period': self.period,
                                'team': puck_team_name, 'player': shooter,
                                'event': 'Shot'})
        elif _empty_net or random.random() < shot_chance:
            shot_result = 'GOAL'
            self.score[puck_team_name] += 1
            # Structured drama (workstream B, 2026-09-30, additive):
            # detect the empty-net conversion and the late equalizer while
            # the pulled state is still live (before _return_all_goalies).
            try:
                from drama_events import (record_late_equalizer as _rle_q,
                                          record_empty_net_goal as _reng_q)
                _pulled_live_q = set(getattr(self, "goalie_pulled", set()) or set())
                if _empty_net:
                    _reng_q(self, puck_team_name, shooter)
                elif (self.period == 3 and puck_team_name in _pulled_live_q):
                    _pre_q = self.score[puck_team_name] - 1
                    _opp_q = (self.away_team.team_name if puck_team_name
                              == self.home_team.team_name
                              else self.home_team.team_name)
                    if _pre_q == self.score[_opp_q] - 1:
                        _rle_q(self, puck_team_name, shooter,
                               pull_clock_remaining=getattr(
                                   self, "_pull_clock", {}).get(puck_team_name))
            except Exception:
                pass
            # D1 design build: goals move benches (conceding coach
            # re-evaluates -- same shared decision as the watched path).
            try:
                self._refresh_coach_instructions(
                    flags_by_team={opp_team_name: {"goal_against"}})
            except Exception:
                pass
            # The net is never empty across a goal: both goalies return.
            self._return_all_goalies()
            # Crowd: the building swings on every goal (live mood/energy).
            self._crowd_on_goal(puck_team_name)
            # Update stats
            self.stats[puck_team_name][shooter.id]['goals'] = self.stats[puck_team_name][shooter.id].get('goals', 0) + 1
            # Charge the goal to the beaten goalie's game line (empty-netters
            # don't count) -- feeds the last-10 performance grade ledger.
            if not _empty_net and goalie is not None:
                try:
                    _gd = self.stats[opp_team_name][goalie.id]
                    _gd['goals_against'] = _gd.get('goals_against', 0) + 1
                except Exception:
                    pass
            # Goalie personality: charge the goal to the beaten goalie --
            # bounce-back clock starts, tilt check for shelled battlers.
            # Same shared decision as GameSim (empty-netters don't count).
            if not _empty_net and goalie is not None:
                try:
                    import goalie_personality as _gp2
                    _st2 = self.goalie_personality_state.get(goalie.id)
                    if _st2 is None:
                        _st2 = _gp2.new_game_state()
                        self.goalie_personality_state[goalie.id] = _st2
                    _gp2.record_goal_allowed(_st2)
                    _gp2.check_tilt(goalie, _st2)
                except Exception:
                    pass
            # Assists: primary = last successful passer to the shooter
            # (tracked as assist_potential on passes); secondary = a random
            # on-ice teammate, the way real scoring works.
            assist_ids, assist_players = self._credit_assists(shooter, puck_team_name)
            # Add goal event
            self.events.append({'time': self.time, 'period': self.period, 'team': puck_team_name,
                                'player': shooter, 'event': 'Goal', 'assists': assist_players})
            if self.pp_team == puck_team_name:
                _strength = 'PP'
            elif self.pk_team == puck_team_name:
                _strength = 'SH'
            else:
                _strength = 'EV'
            _in_period = max(0.0, self.time - 1200 * (self.period - 1))
            self.event_log.append({
                'timestamp': self.time,
                'duration': 1.0,
                'type': 'GOAL_ADVANCED',
                'details': {
                    'scorer_id': shooter.id,
                    'assist_ids': assist_ids,
                    'goaltender_id': goalie.id if goalie else None,
                    'goal_type': 'empty_net' if _empty_net else shot_type,
                    'period': self.period,
                    'strength': _strength,
                    'time_str': f"{int(_in_period // 60)}:{int(_in_period % 60):02d}",
                }
            })
            # PP ends when the PP team scores (NHL rule)
            if self.pp_team == puck_team_name:
                self.pp_team = None
                self.pk_team = None
                self.pp_end_time = None
        elif goalie:
            # On-net but stopped. The miss was decided upfront (D11/RC1);
            # a shot reaching here passed the shared miss gate, so it is
            # always a SAVE -- the old post-hoc miss re-roll is gone.
            shot_result = 'SAVE'
            if goalie:
                self.stats[opp_team_name][goalie.id]['saves'] = self.stats[opp_team_name][goalie.id].get('saves', 0) + 1
            # Add shot/save event
            self.events.append({'time': self.time, 'period': self.period, 'team': puck_team_name, 'player': shooter, 'event': 'Shot'})
            # D12 discrete rebound event (2026-09-30, Muck: quick sim must
            # behave the SAME as the watched sim): a real save (not a miss)
            # can kick out a rebound -- the fast approximation of
            # GameSim._resolve_rebound_chance, wired below.
            if shot_result == 'SAVE':
                self._resolve_rebound_event(goalie, puck_team_name,
                                            opp_team_name, shot_type, shooters)
        else:
            shot_result = 'MISS'
            # Add missed shot event
            self.events.append({'time': self.time, 'period': self.period, 'team': puck_team_name, 'player': shooter, 'event': 'Shot'})
            
        # Update shot stats
        self.stats[puck_team_name][shooter.id]['shots'] = self.stats[puck_team_name][shooter.id].get('shots', 0) + 1
        # Chance-grade analytics (2026-09-28, per Muck): record the grade
        # on every shot attempt -- the xG backbone. grade_a/b/c_shots and
        # grade_a/b/c_goals per player; expected goals falls out as
        # sum(shots_g * league_avg_conversion_g).
        try:
            _ag = str(getattr(self, "_last_chance_grade", "B") or "B").upper()
            if _ag not in ("A", "B", "C"):
                _ag = "B"
            _st = self.stats[puck_team_name][shooter.id]
            _sk = f'grade_{_ag.lower()}_shots'
            _st[_sk] = _st.get(_sk, 0) + 1
            if shot_result == 'GOAL':
                _gk = f'grade_{_ag.lower()}_goals'
                _st[_gk] = _st.get(_gk, 0) + 1
        except Exception:
            pass
        # Analytics integration (2026-10-01): lightweight shot-level log
        # for the Analytics Hub -- the fast approximation of GameSim's
        # shot records. Grade, xg from the canonical grade value, the
        # scenario/composite chance context, and the outcome. Additive.
        try:
            from mesh_system import grade_xg_value as _gxv_qs
            _qxg = _gxv_qs(_ag)
        except Exception:
            _qxg = 0.08
        try:
            _qcctx = dict(getattr(self, "_last_chance_context", None) or {})
        except Exception:
            _qcctx = {}
        try:
            _qoutcome = {"GOAL": "goal", "SAVE": "save",
                         "MISS": "miss"}.get(shot_result, "blocked")
            self._analytics_shots.append({
                "shooter_id": getattr(shooter, "id", None),
                "shooter": getattr(shooter, "full_name",
                                   getattr(shooter, "name", "?")),
                "team": puck_team_name,
                "opp": opp_team_name,
                "period": int(getattr(self, "period", 1) or 1),
                "clock": round(float(getattr(self, "time", 0) or 0), 1),
                "location": str(shot_type or ""),
                "x": 0.0, "y": 0.0,
                "distance": 0.0,
                "shot_type": str(shot_type or ""),
                "xg": round(float(_qxg), 3),
                "grade": _ag,
                "chance_context": _qcctx,
                "outcome": _qoutcome,
                "line": "-",
            })
        except Exception:
            pass
        
        # Log event
        self.event_log.append({
            'timestamp': self.time,
            'duration': duration,
            'type': 'SHOT',
            'details': {
                'shooter_id': shooter.id,
                'shot_type': shot_type,
                'puck_start_pos': shot_start,
                'result': shot_result,
                'chance_grade': str(getattr(self, "_last_chance_grade", "B") or "B").upper(),
            }
        })
        
        # Add stoppage if needed
        if shot_result in ['GOAL', 'SAVE']:
            self.event_log.append({
                'timestamp': self.time + duration,
                'duration': 2.0 if shot_result == 'GOAL' else 1.5,
                'type': 'STOPPAGE',
                'details': {
                    'reason': 'Goal Scored' if shot_result == 'GOAL' else 'Save',
                    'faceoff_pos': (50, 25)
                }
            })

    def _resolve_rebound_event(self, goalie, puck_team_name, opp_team_name,
                               shot_type, shooters):
        """Discrete rebound event (D12 quick-sim wiring, 2026-09-30, Muck).

        Fast approximation of GameSim._resolve_rebound_chance -- the SAME
        trigger ladder, the SAME finisher pick and net-front battle, and
        the SHARED mesh_system.netfront_finish_chance decision (never a
        different formula). Rebounds are grade A by the shared hard gate.
        Returns True when a rebound chance resolved (goal or save).
        """
        # --- finisher pool: on-ice attackers, goalie excluded -----------
        _attackers = [p for p in (shooters or [])
                      if p is not None
                      and getattr(getattr(p, "primary_position", None),
                                  "name", "") != "GOALIE"]
        if not _attackers:
            return False

        # --- trigger: GameSim's rebound-control ladder, fast form -------
        # GameSim._determine_rebound_control computes control_probability
        # and fires the rebound chance on WEAK_REBOUND/DANGEROUS_REBOUND
        # (P = 1 - control_probability). Rungs resolve as plain indices
        # here (the enum lives in simulation.py); the ladder math is
        # identical: absorbed < cp*0.45, controlled < cp*0.75,
        # deflected_away < cp, weak < cp + (1-cp)*0.7, else dangerous.
        _rc = float(getattr(goalie, "rebound_control", 69.0) or 69.0) \
            if goalie is not None else 69.0
        _base = min(0.97, max(0.50, 0.80 + (_rc - 69.0) * 0.008))
        # PROXY (documented): quick_sim does not model save types, so the
        # GameSim save-type modifier (0.4-1.3 across glove/chest/stick/
        # pad/blocker/desperation/diving) is replaced by its expected
        # value over GameSim's own save-type distribution (base: glove
        # .2/chest .15/stick .1/pad .3/blocker .2/desperation .04/diving
        # .01 -> 1.3*.2+1.2*.15+0.7*.1+0.8*.3+0.6*.2+0.4*.04+0.5*.01
        # = 0.89). The shot-type modifier mirrors GameSim's table
        # exactly (slap 0.7, one-timer 0.6, tip 0.5, deflection 0.4).
        _shot_mod = {"slap shot": 0.7, "one-timer": 0.6,
                     "tip": 0.5, "deflection": 0.4}.get(shot_type, 1.0)
        _cp = min(_base * 0.89 * _shot_mod, 0.97)
        _r = random.random()
        _rung = (0 if _r < _cp * 0.45 else
                 1 if _r < _cp * 0.75 else
                 2 if _r < _cp else
                 3 if _r < _cp + (1.0 - _cp) * 0.7 else 4)
        # Goalie personality: the same rebound_shift GameSim applies --
        # athletic scramblers kick out more second chances, technicians
        # swallow pucks. Shifts the outcome one rung up/down the ladder.
        try:
            import goalie_personality as _gp_rb
            _shift = (float(_gp_rb.rebound_shift(goalie))
                      if goalie is not None else 0.0)
            if _shift > 0 and random.random() < _shift:
                _rung = min(4, _rung + 1)
            elif _shift < 0 and random.random() < -_shift:
                _rung = max(0, _rung - 1)
        except Exception:
            pass
        if _rung < 3:
            return False  # controlled: no rebound, play continues

        # --- the goalie kicked this puck out: he created the rebound ----
        # (mirrors GameSim: debited before the scramble, on both
        # branches; never raises on goalie-less synthetic setups)
        if goalie is not None:
            _gst = self.stats[opp_team_name].setdefault(goalie.id, {})
            _gst['rebounds_created'] = _gst.get('rebounds_created', 0) + 1

        # --- finisher pick + net-front battle (GameSim's formula) -------
        # Same weights GameSim uses (no proxy needed: shooters IS the
        # on-ice attacking group): anticipation + offensive_awareness.
        # Then the same scramble: attacker roll vs best defender roll --
        # the forward-vs-defense half of forward vs (defense + goalie).
        _finisher = random.choices(
            _attackers,
            weights=[max(1.0,
                         float(getattr(p, "anticipation", 10) or 10)
                         + float(getattr(p, "offensive_awareness", 10) or 10))
                     for p in _attackers],
            k=1)[0]
        try:
            _d_onice = ((self.on_ice.get(opp_team_name, {}) or {})
                        .get("Defense", []))
            _defenders = [d for d in _d_onice if d is not None]
        except Exception:
            _defenders = []
        _best_def = (max(_defenders,
                         key=lambda p: (float(getattr(p, "anticipation", 10)
                                              or 10)
                                        + float(getattr(p, "defensive_awareness",
                                                        10) or 10)))
                     if _defenders else None)
        _att_roll = (float(getattr(_finisher, "anticipation", 10) or 10)
                     + float(getattr(_finisher, "offensive_awareness", 10)
                             or 10) + random.randint(1, 10))
        _def_roll = ((float(getattr(_best_def, "anticipation", 10) or 10)
                      + float(getattr(_best_def, "defensive_awareness", 10)
                              or 10) + random.randint(1, 10))
                     if _best_def is not None else 0)
        if not (_att_roll > _def_roll):
            return False  # defender clears it: play continues, nothing
                          # invented (quick_sim has no possession model
                          # on this path)

        # --- the shared decision: forward vs goalie --------------------
        # goalie_skill is computed exactly as in GameSim's D12 hunk
        # (overall_rating, 60.0 fallback); netfront_finish_chance never
        # raises and returns within [0.05, 0.55].
        try:
            from mesh_system import netfront_finish_chance as _nffc
            _gs = 60.0
            try:
                _ov = getattr(goalie, "overall_rating", None)
                if callable(_ov):
                    _gs = float(_ov())
                elif _ov is not None:
                    _gs = float(_ov)
            except Exception:
                pass
            _nf_p = float(_nffc(_finisher, goalie, _gs))
        except Exception:
            _nf_p = 0.22
        _reb_goal = random.random() < _nf_p

        # --- the rebound is its own shot: grade A by the hard gate -----
        _fst = self.stats[puck_team_name].setdefault(_finisher.id, {})
        _fst['shots'] = _fst.get('shots', 0) + 1
        _fst['grade_a_shots'] = _fst.get('grade_a_shots', 0) + 1
        self.events.append({'time': self.time, 'period': self.period,
                            'team': puck_team_name, 'player': _finisher,
                            'event': 'Shot'})

        if _reb_goal:
            # Rebound goal -- credited exactly as the quick_sim goal path.
            _fst['goals'] = _fst.get('goals', 0) + 1
            _fst['grade_a_goals'] = _fst.get('grade_a_goals', 0) + 1
            _fst['rebounds_scored'] = _fst.get('rebounds_scored', 0) + 1
            self.score[puck_team_name] += 1
            # The net is never empty across a goal: both goalies return.
            self._return_all_goalies()
            # Crowd: the building swings on every goal.
            self._crowd_on_goal(puck_team_name)
            # Goalie personality: charge the goal to the beaten goalie --
            # bounce-back clock starts, tilt check for shelled battlers.
            if goalie is not None:
                try:
                    import goalie_personality as _gp2r
                    _st2 = self.goalie_personality_state.get(goalie.id)
                    if _st2 is None:
                        _st2 = _gp2r.new_game_state()
                        self.goalie_personality_state[goalie.id] = _st2
                    _gp2r.record_goal_allowed(_st2)
                    _gp2r.check_tilt(goalie, _st2)
                except Exception:
                    pass
                # Same game-line charge as the main goal path (rebound goals
                # never beat an empty net): feeds the performance ledger.
                try:
                    _gd = self.stats[opp_team_name][goalie.id]
                    _gd['goals_against'] = _gd.get('goals_against', 0) + 1
                except Exception:
                    pass
            # Assists: the finisher is the scorer of the rebound goal.
            assist_ids, assist_players = self._credit_assists(_finisher,
                                                              puck_team_name)
            self.events.append({'time': self.time, 'period': self.period,
                                'team': puck_team_name, 'player': _finisher,
                                'event': 'Goal', 'assists': assist_players})
            if self.pp_team == puck_team_name:
                _strength = 'PP'
            elif self.pk_team == puck_team_name:
                _strength = 'SH'
            else:
                _strength = 'EV'
            _in_period = max(0.0, self.time - 1200 * (self.period - 1))
            self.event_log.append({
                'timestamp': self.time,
                'duration': 1.0,
                'type': 'GOAL_ADVANCED',
                'details': {
                    'scorer_id': _finisher.id,
                    'assist_ids': assist_ids,
                    'goaltender_id': goalie.id if goalie else None,
                    'goal_type': 'rebound',
                    'period': self.period,
                    'strength': _strength,
                    'time_str': f"{int(_in_period // 60)}:{int(_in_period % 60):02d}",
                }
            })
            # PP ends when the PP team scores (NHL rule)
            if self.pp_team == puck_team_name:
                self.pp_team = None
                self.pk_team = None
                self.pp_end_time = None
            self.event_log.append({
                'timestamp': self.time + 1.0,
                'duration': 2.0,
                'type': 'STOPPAGE',
                'details': {'reason': 'Goal Scored', 'faceoff_pos': (50, 25)}
            })
        else:
            # Rebound saved -- the goalie stops the second chance too
            # (GameSim credits this save on its rebound path); play
            # continues, no invented second-order events.
            if goalie is not None:
                _gst2 = self.stats[opp_team_name].setdefault(goalie.id, {})
                _gst2['saves'] = _gst2.get('saves', 0) + 1
        return True

    def _calculate_goalie_save_skill(self, goalie, shot_type, danger_level=None, distance=None, situation=None):
        """Enhanced goalie skill calculation with coordinate-based danger awareness.

        The base is the ONE shared composite (divergence #5) -- the same
        .40/.25/.20/.10/.05 weighting GameSim now uses. Situational model
        (2026-09-28, per Muck): when `situation` is given ('screened',
        'tip', 'breakaway', 'point', 'clean'), the shared
        situational_goalie_skill re-weights (screened leans positioning+
        composure, tips lean reflexes, etc.).
        """
        if not goalie:
            return 8.0

        if situation:
            try:
                from mesh_system import situational_goalie_skill as _sgs
                base_skill = _sgs(goalie, situation)
            except Exception:
                from mesh_system import goalie_skill_composite as _gsc
                base_skill = _gsc(goalie)
        else:
            from mesh_system import goalie_skill_composite as _gsc
            base_skill = _gsc(goalie)
        
        # Danger level adjustments for coordinate-based analysis
        if danger_level:
            danger_penalties = {
                'very_high': -4,  # Very hard saves in high danger
                'high': -2,       # Moderately difficult
                'medium': 0,      # Neutral
                'low': 2          # Easier saves from distance/bad angles
            }
            base_skill += danger_penalties.get(danger_level, 0)
        
        # Shot type specific adjustments
        shot_type_modifiers = {
            'one-timer': -3,      # Quick shots harder to stop
            'wrist shot': 0,      # Standard
            'slap shot': 1,       # Easier to see coming
            'backhand': -1,       # Deceptive
            'tip': -4,            # Very difficult
            'deflection': -3      # Hard to react to
        }
        base_skill += shot_type_modifiers.get(shot_type, 0)
        
        # Distance factor for coordinate analysis
        if distance:
            if distance < 15:
                base_skill -= 2  # Close shots harder
            elif distance > 35:
                base_skill += 1  # Long shots easier
        
        # Legacy adjustments for compatibility
        if shot_type == "slap shot":
            base_skill += getattr(goalie, 'glove_hand', 10) * 0.05
        elif shot_type == "one-timer":
            base_skill += getattr(goalie, 'reflexes', 10) * 0.05
        elif shot_type == "backhand":
            base_skill += getattr(goalie, 'positioning', 10) * 0.05
        elif shot_type == "breakaway":
            base_skill += getattr(goalie, 'breakaway_skill', 10) * 0.1
            
        return max(5, base_skill)
    
    def _block_unit(self, defending_team_name):
        """D11: resolve the defending unit's block components ONCE per unit
        composition: (blocker, unit_battle, unit_tendency, unit_composite)
        for approx_shot_fate. The D corps does not change within a QS
        shift, so the cached resolution is exact while the unit is
        unchanged; any lineup change produces a new cache key (self-
        invalidating). The composite is called WITHOUT energy, exactly
        as GameSim's block path calls it. Never raises; returns
        (None, None, 1.0, 1.0) when unusable.
        """
        try:
            from mesh_system import (resolve_blocker as _rb,
                                     defensive_positioning as _dp)
            _corps = [d for d in (self.on_ice.get(defending_team_name, {})
                                  or {}).get("Defense", []) if d]
            if not _corps:
                return (None, None, 1.0, 1.0)
            _key = (defending_team_name,
                    tuple(sorted(getattr(d, "id", 0) for d in _corps)))
            try:
                _hit = self._block_unit_cache.get(_key)
            except Exception:
                _hit = None
            if _hit is not None:
                return _hit
            try:
                from player_archetypes import get_tendency as _gt
                _w = {d: max(0.05, _gt(d, "block")) for d in _corps}
            except Exception:
                _w = None
            _blocker = _rb(_corps, weights=(_w.get if _w else None))
            if _blocker is None:
                _res = (None, None, 1.0, 1.0)
            else:
                _ubattle = (_dp(_blocker) * 0.50
                            + float(getattr(_blocker, "shot_blocking", 10)) * 0.50)
                _utend = float(_w.get(_blocker, 1.0)) if _w else 1.0
                try:
                    from attribute_composites import (
                        apply_amplifier as _ac)
                    _ucomp = _ac(1.0, _blocker, "defensive_play",
                                 sim=self, team=defending_team_name)
                except Exception:
                    _ucomp = 1.0
                _res = (_blocker, _ubattle, _utend, _ucomp)
            try:
                self._block_unit_cache[_key] = _res
            except Exception:
                pass
            return _res
        except Exception:
            return (None, None, 1.0, 1.0)

    def _resolve_pass_event(self, passer, shooters, puck_team_name, opp_team_name, fatigue_factor):
        """Enhanced pass resolution"""
        if len(shooters) <= 1:
            return
            
        # Part B: the setup man finds the FINISHER -- weight the receiver
        # by finishing (the shared shooter_choice_weight) x relationship
        # closeness with the passer. Same decision GameSim makes.
        _rcands = [p for p in shooters if p != passer]
        if not _rcands:
            return
        try:
            from player_archetypes import shooter_choice_weight as _scw5
            from mesh_system import relationship_mult as _relm2
            _rw5 = [max(0.05, _scw5(_c) * _relm2(passer, _c))
                    for _c in _rcands]
            receiver = random.choices(_rcands, weights=_rw5, k=1)[0]
        except Exception:
            receiver = random.choice(_rcands)
        
        # Calculate pass skill
        pass_skill = (
            getattr(passer, 'passing_accuracy', 10) * 0.3 +
            getattr(passer, 'passing_creativity', 10) * 0.25 +
            getattr(passer, 'vision', 10) * 0.2 +
            getattr(passer, 'off_the_puck', 10) * 0.15 +
            getattr(passer, 'hockey_iq', 10) * 0.1
        ) * fatigue_factor
        
        # Defensive pressure
        defenders = [p for p in self.on_ice[opp_team_name]['Defense'] if p]
        defender = random.choice(defenders) if defenders else None
        
        defense_skill = (
            getattr(defender, 'pokecheck', 10) * 0.4 +
            getattr(defender, 'defensive_awareness', 10) * 0.4 +
            getattr(defender, 'anticipation', 10) * 0.2
        ) if defender else 10
        # Installed systems: a pressing team's forecheck gets home more
        # often -- swarm/counter-press defenders break up more passes.
        try:
            _mm = self._systems_matchup or {}
            _mh = opp_team_name == self.home_team.team_name
            defense_skill *= _mm.get("home_pressure" if _mh else "away_pressure", 1.0)
        except Exception:
            pass
        
        pass_success = pass_skill > defense_skill or random.random() < 0.7

        # WS4 H3 -- forecheck strip-back (GameSim simulation.py:3025 DZ /
        # 8822 OZ swarm, fast fidelity): when the PP coughs the puck up,
        # the 5-man forecheck hunts it -- numbers + structure tell. A
        # well-drilled unit strips the interceptor and goes back to work;
        # a malformed one gets burned the other way (shorthanded rush).
        # GameSim's strip shape: (hunter / (hunter + carrier)) * 1.08 *
        # the shared sustenance. EV passes are untouched.
        _sh_rush = False
        try:
            if (not pass_success and defender is not None
                    and getattr(self, "pp_team", None) == puck_team_name):
                _sus3 = self._pp_forecheck_sustenance()
                _pp_onice3 = (self.on_ice.get(puck_team_name, {}) or {})
                _pp_unit3 = [p for p in (
                    (_pp_onice3.get("Forwards", []) or [])
                    + (_pp_onice3.get("Defense", []) or [])) if p]
                if _pp_unit3:
                    _hunter3 = max(
                        _pp_unit3,
                        key=lambda pl: (float(getattr(pl, "checking", 10)
                                             or 10)
                                        + float(getattr(pl, "anticipation",
                                                        10) or 10)))
                    _hs3 = (float(getattr(_hunter3, "checking", 10) or 10)
                            + float(getattr(_hunter3, "anticipation", 10)
                                    or 10)
                            + float(getattr(_hunter3, "skating", 10) or 10)
                            ) / 3.0
                    _cs3 = (float(getattr(defender, "puck_handling", 10)
                                  or 10)
                            + float(getattr(defender, "composure", 10)
                                    or 10)
                            + float(getattr(defender, "skating", 10) or 10)
                            ) / 3.0
                    _strip3 = ((_hs3 / max(1.0, _hs3 + _cs3)) * 1.08
                               * _sus3)
                    if random.random() < _strip3:
                        # Stripped back -- the PP retains, play continues.
                        pass_success = True
                    else:
                        # Burned -- the interceptor walks in shorthanded.
                        _sh_rush = True
                    _wh3 = getattr(self, "_ws4_scenario_hits", None)
                    if _wh3 is None:
                        _wh3 = self._ws4_scenario_hits = {}
                    _wh3["pp_strip_back"] = _wh3.get("pp_strip_back", 0) + 1
        except Exception:
            pass

        # Log pass event
        puck_start = (passer.x, passer.y)
        puck_end = (receiver.x, receiver.y)
        duration = random.uniform(0.7, 1.2)
        
        self.event_log.append({
            'timestamp': self.time,
            'duration': duration,
            'type': 'PASS',
            'details': {
                'passer_id': passer.id,
                'receiver_id': receiver.id,
                'puck_start_pos': puck_start,
                'puck_end_pos': puck_end,
                'success': pass_success
            }
        })
        
        # Move puck
        if pass_success:
            self.puck_x, self.puck_y = puck_end
            # Update assist potential
            if hasattr(receiver, 'assist_potential'):
                receiver.assist_potential = passer.id
        else:
            if defender:
                self.puck_x, self.puck_y = defender.x, defender.y

        # WS4 H3 (cont.): the strip-back lost -- the interceptor's
        # shorthanded rush resolves immediately, before the next event.
        if _sh_rush and defender is not None:
            try:
                self._resolve_sh_rush_event(defender, puck_team_name,
                                             opp_team_name,
                                             self._pp_forecheck_sustenance())
            except Exception:
                pass
    
    def _resolve_sh_rush_event(self, rusher, pp_team_name, pk_team_name,
                               sus):
        """Shorthanded rush off a burned PP pass (WS4 H3/H4).

        The forecheck's strip-back lost, so the interceptor walks in
        alone on the PP's goalie. Resolves through the standard shot
        path (grades, goalie, impacts all apply); the PP's structure
        suppresses the look via sh_rush_sus (WS4 H4 -- GameSim's
        1.0 + 0.42*(sus-0.68) rush-defense shape). The PP continues
        afterward (no goal was scored by the PP team).
        """
        try:
            _pp_goalie = (self.on_ice.get(pp_team_name, {}) or {}).get(
                "Goalie")
            _pk_onice = self.on_ice.get(pk_team_name, {}) or {}
            _pk_skaters = [p for p in (
                (_pk_onice.get("Forwards", []) or [])
                + (_pk_onice.get("Defense", []) or [])) if p]
            if rusher is None:
                return
            _ff = self._calculate_fatigue_factor(rusher, pk_team_name)
            _pm = self._calculate_pressure_modifier(rusher)
            _pf = self._calculate_position_factor(rusher, pk_team_name)
            self.events.append({
                'time': self.time, 'period': self.period,
                'team': pk_team_name, 'player': rusher,
                'event': 'Shorthanded Rush'})
            self._resolve_shot_event(rusher, _pp_goalie, pk_team_name,
                                     pp_team_name, _ff, _pm, _pf,
                                     _pk_skaters, sh_rush_sus=sus)
        except Exception:
            pass

    def _resolve_deke_event(self, deker, puck_team_name, fatigue_factor):
        """Resolve deke attempt -- the 1v1 rush battle, fast fidelity.

        The deker takes on the NEAREST checker (not a random defender
        across the ice), exactly the battle GameSim runs in
        _determine_next_event. The shared rush_chance scenario
        (scenario_composites) resolves it -- skating / chance_creation /
        finishing vs defensive_play / goalie_save -- REPLACING the old
        skating single-composite hook (§6 rule 2: the scenario already
        contains those composites; never stack).
        """
        deke_skill = (
            getattr(deker, 'stickhandling', 10) * 0.4 +
            getattr(deker, 'agility', 10) * 0.3 +
            getattr(deker, 'anticipation', 10) * 0.3
        ) * fatigue_factor
        # --- rush_chance scenario (shared battle, 2026-10-01 WS4) ---
        # One decision, two fidelities: the same apply_scenario call
        # shape GameSim uses (attacker-side player vs defender-side
        # player, sim + team context). The battle multiplies the deke
        # roll inside the scenario's rails -- no local reimplementation.
        try:
            from scenario_composites import apply_scenario as _asc_deke
            _opp_deke = (self.away_team
                         if puck_team_name == self.home_team.team_name
                         else self.home_team)
            _dskaters = [p for p in (
                (self.on_ice.get(_opp_deke.team_name, {}) or {})
                .get("Forwards", []) or []) if p]
            _dskaters += [p for p in (
                (self.on_ice.get(_opp_deke.team_name, {}) or {})
                .get("Defense", []) or []) if p]
            _dpos0 = self.coordinate_engine.player_positions.get(
                getattr(deker, "id", None), (100, 42.5))

            def _ddist(_d):
                try:
                    _pp = self.coordinate_engine.player_positions.get(
                        getattr(_d, "id", None), (100, 42.5))
                    return ((_pp[0] - _dpos0[0]) ** 2
                            + (_pp[1] - _dpos0[1]) ** 2)
                except Exception:
                    return 1e18

            _near = min(_dskaters, key=_ddist, default=None)
            deke_skill = _asc_deke(
                deke_skill, [deker],
                [_near] if _near is not None else [],
                "rush_chance", sim=self,
                off_team=puck_team_name, def_team=_opp_deke.team_name)
            _wh = getattr(self, "_ws4_scenario_hits", None)
            if _wh is None:
                _wh = self._ws4_scenario_hits = {}
            _wh["rush_chance"] = _wh.get("rush_chance", 0) + 1
        except Exception:
            pass

        if deke_skill > 12:
            self.events.append({
                'time': self.time, 'period': self.period, 
                'team': puck_team_name, 'player': deker, 
                'event': 'Successful Deke'
            })
    
    def _resolve_puck_battle(self, shooters, puck_team_name, fatigue_factor):
        """Resolve puck battle between teammates"""
        if len(shooters) < 2:
            return
            
        battlers = random.sample(shooters, 2)
        p1, p2 = battlers
        
        p1_skill = (
            getattr(p1, 'strength', 10) * 0.25 +
            getattr(p1, 'aggressiveness', 10) * 0.2 +
            getattr(p1, 'balance', 10) * 0.2 +
            getattr(p1, 'work_rate', 10) * 0.2 +
            getattr(p1, 'loose_puck', 10) * 0.15
        ) * fatigue_factor
        
        p2_skill = (
            getattr(p2, 'strength', 10) * 0.25 +
            getattr(p2, 'aggressiveness', 10) * 0.2 +
            getattr(p2, 'balance', 10) * 0.2 +
            getattr(p2, 'work_rate', 10) * 0.2 +
            getattr(p2, 'loose_puck', 10) * 0.15
        ) * fatigue_factor
        # --- attribute composites (additive, bounded) ---
        # Puck-retrieval composite: the full battle toolkit on both
        # sides. Rails [0.94, 1.06].
        try:
            from attribute_composites import apply_amplifier as _ac_qpb
            p1_skill = _ac_qpb(p1_skill, p1, "puck_retrieval", sim=self,
                              team=puck_team_name, energy=fatigue_factor * 100)
            p2_skill = _ac_qpb(p2_skill, p2, "puck_retrieval", sim=self,
                              team=puck_team_name, energy=fatigue_factor * 100)
        except Exception:
            pass
        
        winner = p1 if p1_skill >= p2_skill else p2
        self.events.append({
            'time': self.time, 'period': self.period, 
            'team': puck_team_name, 'player': winner, 
            'event': 'Puck Battle Won'
        })
    
    def _resolve_screen_event(self, screener, shooters, puck_team_name):
        """Resolve screening attempt -- net-front battle, stage 1+2.

        The screener must WIN the spot (off_the_puck + strength/balance vs
        the defender's box-out) before the screen counts. A won screen
        degrades the goalie's sightline (goalie-side penalty via the shared
        screen_goalie_mult) on the next shot, not a shooter bonus. The
        screen is consumed by the next shot from that team.
        """
        try:
            from mesh_system import (netfront_spot_win as _spot,
                                     screen_goalie_mult as _sgm)
            # Find the defending team's on-ice D to battle for the spot
            _def_team = (self.away_team if puck_team_name == self.home_team.team_name
                         else self.home_team)
            _d_onice = [d for d in (self.on_ice.get(_def_team.team_name, {}) or {}).get("Defense", []) if d]
            _defender = _d_onice[0] if _d_onice else None
            if random.random() < _spot(screener, _defender):
                # Won the spot -- screen is set. Goalie penalty computed
                # at shot time (needs the goalie), stored for next shot.
                if not hasattr(self, "_active_screens"):
                    self._active_screens = {}
                self._active_screens[puck_team_name] = screener
                self.events.append({
                    'time': self.time, 'period': self.period,
                    'team': puck_team_name, 'player': screener,
                    'event': 'Screen Set'
                })
            # Lost the battle: no screen, no event (play continues)
        except Exception:
            pass
    
    def _resolve_deflection_event(self, deflector, shooters, goalie, puck_team_name, opp_team_name):
        """Resolve deflection attempt -- net-front battle, stages 1+3.

        Staged (shared decisions): (1) WIN THE SPOT -- the tipper must beat
        the defender's box-out (netfront_spot_win); can't tip what you
        didn't get to. (2) TIP -- deflections/hand-eye vs goalie reaction
        (tip_goal_chance), with the screen bonus if a screen is active.
        Replaces the old flat-25% vs goalie. Harmonic-style gating: a
        missing piece hurts.
        """
        try:
            from mesh_system import (netfront_spot_win as _spot,
                                     tip_goal_chance as _tip,
                                     defense_point_shot_discount as _dpsd,
                                     archetype_finish_tilt as _aft)
            # Stage 1: win the spot vs the on-ice defender's box-out
            _def_team = (self.away_team if puck_team_name == self.home_team.team_name
                         else self.home_team)
            _d_onice = [d for d in (self.on_ice.get(_def_team.team_name, {}) or {}).get("Defense", []) if d]
            _defender = _d_onice[0] if _d_onice else None
            if random.random() >= _spot(deflector, _defender):
                return  # boxed out -- no tip
            # Grade analytics: the won spot makes this a grade-A attempt
            # whether or not the tip converts.
            try:
                _ds = self.stats[puck_team_name][deflector.id]
                _ds['grade_a_shots'] = _ds.get('grade_a_shots', 0) + 1
            except Exception:
                pass
            # Stage 2: the tip itself (screen bonus if a screen is active)
            _screens = getattr(self, "_active_screens", {}) or {}
            _screened = puck_team_name in _screens
            _gskill = self._calculate_goalie_save_skill(goalie, "deflection") if goalie else 8
            goal_chance = _tip(deflector, goalie, _gskill, screened=_screened)
            # D discount + sniper tilt still apply (a D deflecting his own
            # point shot doesn't get forward conversion)
            goal_chance *= _dpsd(deflector) * _aft(deflector)
            # --- netfront_scramble scenario (shared battle, 2026-10-01 WS4)
            # ---
            # The tip/deflection converts through the netfront_scramble
            # battle -- forward vs (defense + goalie) combined, exactly as
            # GameSim resolves TIP_IN/DEFLECTION/REBOUND shots in its main
            # shot resolution. Same apply_scenario call shape (shooter vs
            # goalie + the spot-battle defender). EV only, never on the PP
            # and never into an empty net -- mirrors the watched call-site
            # gating. One scenario per event; the spot-win above is the
            # chance-earning gate, this is the conversion battle.
            try:
                if self.pp_team is None and goalie is not None:
                    from scenario_composites import (
                        apply_scenario as _asc_nf)
                    _dside_nf = [goalie]
                    if _defender is not None:
                        _dside_nf.append(_defender)
                    goal_chance = _asc_nf(
                        goal_chance, [deflector], _dside_nf,
                        "netfront_scramble", sim=self,
                        off_team=puck_team_name,
                        def_team=opp_team_name)
                    _wh2 = getattr(self, "_ws4_scenario_hits", None)
                    if _wh2 is None:
                        _wh2 = self._ws4_scenario_hits = {}
                    _wh2["netfront_scramble"] = _wh2.get(
                        "netfront_scramble", 0) + 1
            except Exception:
                pass

            if random.random() < goal_chance:
                self.score[puck_team_name] += 1
                # D1: tip goals move benches too (same shared decision).
                try:
                    self._refresh_coach_instructions(
                        flags_by_team={opp_team_name: {"goal_against"}})
                except Exception:
                    pass
                self.stats[puck_team_name][deflector.id]['goals'] = self.stats[puck_team_name][deflector.id].get('goals', 0) + 1
                # Net-front goals are a tracked category (QA: netfront_goals)
                try:
                    _nf = self.stats[puck_team_name][deflector.id]
                    _nf['netfront_goals'] = _nf.get('netfront_goals', 0) + 1
                    # Grade-A goal (the attempt was recorded above).
                    _nf['grade_a_goals'] = _nf.get('grade_a_goals', 0) + 1
                except Exception:
                    pass
                self.events.append({
                    'time': self.time, 'period': self.period,
                    'team': puck_team_name, 'player': deflector,
                    'event': 'Deflection Goal'
                })
        except Exception:
            pass
    
    def _check_for_penalty(self, players, puck_team_name, opp_team_name, fatigue_factor):
        """Penalty checking tuned to NHL rates (~3-4 penalties per team per game).

        Called once per game event (~110 events/game), so per-event probability
        of ~6% yields realistic penalty totals. Player discipline/aggressiveness
        and fatigue modulate the chance. Sets a real 2-minute penalty clock.
        """
        if not players:
            return

        penalized = random.choice(players)
        discipline_rating = getattr(penalized, 'discipline', 10)
        aggressiveness = getattr(penalized, 'aggressiveness', 10)

        # Base ~2.2% per check (~250 checks/game -> ~6-8 penalties/game, NHL rate);
        # tired/undisciplined/aggressive players foul more
        base = 0.022 * (2.0 - fatigue_factor)
        discipline_mod = (10 - discipline_rating) * 0.001
        aggr_mod = (aggressiveness - 10) * 0.0008
        penalty_chance = min(0.06, max(0.005, base + discipline_mod + aggr_mod))
        # Installed systems: undisciplined teams (swarm forecheck,
        # net-front crash) foul more; trap/box teams stay out of the box.
        try:
            _mm = self._systems_matchup or {}
            _mh = puck_team_name == self.home_team.team_name
            _disc = _mm.get("home_discipline" if _mh else "away_discipline", 1.0)
            penalty_chance *= max(0.5, min(1.5, 2.0 - _disc))
            penalty_chance = min(0.06, max(0.005, penalty_chance))
        except Exception:
            pass
        # D1 design build: the offending team's instruction moves the
        # penalty rate -- the fast fidelity of the watched path's
        # instruction_penalty_mult on hit results (same shared function,
        # coach-mediated, player from the draw itself). Bounded.
        try:
            from mesh_system import instruction_penalty_mult as _ipm_qs
            _tn = getattr(self, "home_team", None)
            _coach_qs = (getattr(self, "_home_coach", None)
                         if _tn is not None and puck_team_name
                         == getattr(_tn, "team_name", "")
                         else getattr(self, "_away_coach", None))
            _instrs_qs = getattr(self, "_coach_instructions", {}) or {}
            _pm = _ipm_qs(_instrs_qs.get(puck_team_name, ""),
                          player=penalized, coach=_coach_qs)
            if _pm != 1.0:
                penalty_chance *= _pm
                penalty_chance = min(0.06, max(0.005, penalty_chance))
        except Exception:
            pass
        # --- attribute composites (additive, bounded) ---
        # Discipline (inverted): composed decision-makers foul less often.
        # Rails [0.96, 1.04], inverted.
        try:
            from attribute_composites import apply_amplifier as _ac_qpen
            penalty_chance = _ac_qpen(penalty_chance, penalized,
                                     "discipline", sim=self,
                                     team=puck_team_name,
                                     energy=fatigue_factor * 100, invert=True)
        except Exception:
            pass

        if random.random() >= penalty_chance:
            return

        self.stats[puck_team_name][penalized.id]['penalties'] = \
            self.stats[puck_team_name][penalized.id].get('penalties', 0) + 1
        self.events.append({
            'time': self.time, 'period': self.period,
            'team': puck_team_name, 'player': penalized,
            'event': 'Penalty'
        })
        # §5.2: chippy games boil over — feed the shared heat accumulator
        # (penalties are quick-sim's physical proxy; +2 each, cap 40).
        try:
            from scenario_composites import add_live_heat as _alh_q
            _alh_q(self, 2.0)
        except Exception:
            pass
        self.pp_team = opp_team_name
        self.pk_team = puck_team_name
        # 2-minute minor; on a 5-on-3 the PP lasts until the later expiry
        new_expiry = self.time + 120
        self.pp_end_time = new_expiry if not self.pp_end_time else max(self.pp_end_time, new_expiry)

    def get_state(self, step):
        # Defensive: check bounds
        if step < 0 or step >= len(self.state_history):
            return {'players': [], 'puck': {}, 'events': []}
        state = self.state_history[step]
        players = []
        # Home skaters
        for p in state['home']:
            player_obj = next((pl for pl in self.home_team.roster if pl.id == p['id']), None)
            number = player_obj.jersey_number if player_obj else ""
            players.append({'x': p['x'], 'y': p['y'], 'id': p['id'], 'team': 'home', 'number': number})
        # Away skaters
        for p in state['away']:
            player_obj = next((pl for pl in self.away_team.roster if pl.id == p['id']), None)
            number = player_obj.jersey_number if player_obj else ""
            players.append({'x': p['x'], 'y': p['y'], 'id': p['id'], 'team': 'away', 'number': number})
        # Home goalie
        if state['home_goalie']:
            player_obj = next((pl for pl in self.home_team.roster if pl.id == state['home_goalie']['id']), None)
            number = player_obj.jersey_number if player_obj else ""
            players.append({'x': state['home_goalie']['x'], 'y': state['home_goalie']['y'], 'id': state['home_goalie']['id'], 'team': 'home', 'number': number})
        # Away goalie
        if state['away_goalie']:
            player_obj = next((pl for pl in self.away_team.roster if pl.id == state['away_goalie']['id']), None)
            number = player_obj.jersey_number if player_obj else ""
            players.append({'x': state['away_goalie']['x'], 'y': state['away_goalie']['y'], 'id': state['away_goalie']['id'], 'team': 'away', 'number': number})
        puck = {'x': state['puck']['x'], 'y': state['puck']['y']}
        events = []
        for event in self.events:
            if event['event'] == 'Goal' and step == event['time'] // 45:
                events.append(f"Goal by {event['player'].full_name}!")
        return {
            'players': players,
            'puck': puck,
            'events': events
        }
