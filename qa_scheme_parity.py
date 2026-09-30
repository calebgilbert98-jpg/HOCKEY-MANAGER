# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
#!/usr/bin/env python3
"""qa_scheme_parity.py — scheme-bite + chance-origin parity, GameSim vs QuickSim.

Instrument-first (Muck's doctrine): measures, per engine —
  [1] scheme factor application: mean factor + application count for elite
      shooters (ovr>=90), and the location/wheelhouse mix behind it.
  [2] chance origin by position: shooter position/role distribution.
  [3] points by position (center share of top scorers).

Asserts (the (c) acceptance):
  - elite mean scheme factor within 0.01 across engines (same bite),
  - center share of chances within 10pp across engines,
  - no crash / sane totals on either path.

Run: python3 qa_scheme_parity.py   (headless; ~a few minutes)
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collections import Counter, defaultdict

import scenario_composites as sc
from game_classes import League, PlayerPosition
from player_generator import PlayerGenerator

N_GAMES = int(os.environ.get("SCHEME_N", "4"))

SCHEME_LOG = []   # (engine, ovr, pos, role, location, factor)
CHANCE_LOG = []   # (engine, ovr, pos, role)
SCENARIO_LOG = []  # (engine, scenario)

_orig_sffs = sc.schemed_factor_for_shooter


def _wrapped_sffs(shooter, a_on, d_on, location, sim=None,
                  off_team=None, def_team=None):
    f = _orig_sffs(shooter, a_on, d_on, location, sim=sim,
                   off_team=off_team, def_team=def_team)
    try:
        eng = getattr(sim, "_instr_engine", "?")
        ovr = float(shooter.overall_rating())
        pos = getattr(getattr(shooter, "primary_position", None),
                      "name", "?")
        _r = shooter.get_role() if hasattr(shooter, "get_role") else None
        role = getattr(_r, "value", None) or str(_r)
    except Exception:
        ovr, pos, role = -1.0, "?", "?"
    SCHEME_LOG.append((eng, ovr, pos, str(role), str(location), float(f)))
    return f


sc.schemed_factor_for_shooter = _wrapped_sffs

_orig_apply_scenario = sc.apply_scenario


def _wrapped_apply_scenario(base, off_side, def_side, scenario, sim=None,
                            **kw):
    try:
        eng = getattr(sim, "_instr_engine", "?") if sim is not None else "?"
    except Exception:
        eng = "?"
    SCENARIO_LOG.append((eng, str(scenario)))
    return _orig_apply_scenario(base, off_side, def_side, scenario,
                               sim=sim, **kw)


sc.apply_scenario = _wrapped_apply_scenario


def _shooter_info(p):
    try:
        ovr = float(p.overall_rating())
    except Exception:
        ovr = -1.0
    pos = getattr(getattr(p, "primary_position", None), "name", "?")
    try:
        _r = p.get_role() if hasattr(p, "get_role") else None
        role = getattr(_r, "value", None) or str(_r)
    except Exception:
        role = "?"
    return ovr, pos, str(role)


def _pos_bucket(pos):
    p = str(pos).upper()
    if "CENTER" in p:
        return "C"
    if "WING" in p:
        return "W"
    if "DEFEN" in p or p in ("D", "LD", "RD"):
        return "D"
    return "?"


def _boost(p, level):
    """Make a ringer: flat attribute level (drives overall + composites)."""
    for a in ("shooting_accuracy", "shooting_power", "one_timer",
              "offensive_positioning", "defensive_positioning",
              "skating_speed", "agility", "balance", "passing",
              "play_vision", "puck_handling", "faceoffs", "checking",
              "hitting", "shot_blocking", "stick_checking",
              "defensive_awareness", "strength", "aggression",
              "determination", "work_rate", "poise", "adaptability",
              "shot_tendency" if hasattr(p, "shot_tendency") else "shooting_accuracy"):
        try:
            setattr(p, a, level)
        except Exception:
            pass


def make_league():
    random.seed(303)
    league = League("National Hockey League", "NHL")
    gen = PlayerGenerator()
    for team in league.teams[:2]:
        for _ in range(14):
            team.roster.append(gen.create_player(
                position=random.choice([PlayerPosition.CENTER,
                                        PlayerPosition.LEFT_WING,
                                        PlayerPosition.RIGHT_WING]),
                team_name=team.team_name))
        for _ in range(8):
            team.roster.append(gen.create_player(
                position=PlayerPosition.DEFENSE, team_name=team.team_name))
        for _ in range(3):
            team.roster.append(gen.create_player(
                position=PlayerPosition.GOALIE, team_name=team.team_name))
    # Ringers on team 0: generational center (Leblanc stand-in) + elite
    # sniper winger, so the scheme gate (>=90) actually fires.
    h = league.teams[0]
    _cs = [p for p in h.roster
           if getattr(getattr(p, "primary_position", None), "name", "")
           == "CENTER"]
    _ws = [p for p in h.roster if "WING" in
           getattr(getattr(p, "primary_position", None), "name", "")]
    _boost(_cs[0], 97)
    _boost(_ws[0], 95)
    return league, h.team_name


def run_quicksim(league):
    from quick_sim import AdvancedGameSim
    H, A = league.teams[0], league.teams[1]
    _orig = AdvancedGameSim._resolve_shot_event

    def _w(self, shooter, goalie, ptn, otn, ff, pm, pf, shooters):
        CHANCE_LOG.append(("QS",) + _shooter_info(shooter))
        return _orig(self, shooter, goalie, ptn, otn, ff, pm, pf, shooters)
    AdvancedGameSim._resolve_shot_event = _w
    try:
        for i in range(N_GAMES):
            random.seed(1000 + i)
            s = AdvancedGameSim(H, A)
            s._instr_engine = "QS"
            s.run()
    finally:
        AdvancedGameSim._resolve_shot_event = _orig


def run_gamesim(league):
    from simulation import GameSim
    H, A = league.teams[0], league.teams[1]
    _orig = GameSim._resolve_scoring_chance

    def _w(self, shooter, atk, dfn):
        CHANCE_LOG.append(("GS",) + _shooter_info(shooter))
        return _orig(self, shooter, atk, dfn)
    GameSim._resolve_scoring_chance = _w
    try:
        for i in range(N_GAMES):
            random.seed(2000 + i)
            s = GameSim(H, A)
            s._instr_engine = "GS"
            s.run()
    finally:
        GameSim._resolve_scoring_chance = _orig


def main():
    league, hname = make_league()
    print(f"running {N_GAMES} games/engine ...", flush=True)
    run_quicksim(league)
    run_gamesim(league)

    # [1] scheme bite
    print("\n== scheme factor (elite shooters, ovr>=90) ==")
    ok = True
    _means = {}
    for eng in ("QS", "GS"):
        _f = [f for (e, o, p, r, l, f) in SCHEME_LOG
              if e == eng and o >= 90 and f != 1.0]
        _n1 = sum(1 for (e, o, p, r, l, f) in SCHEME_LOG
                  if e == eng and o >= 90)
        _m = sum(_f) / len(_f) if _f else 1.0
        _means[eng] = _m
        print(f"  {eng}: n_elite_apps={_n1} n_nontrivial={len(_f)} "
              f"mean_factor={_m:.4f}")
    if abs(_means.get("QS", 1) - _means.get("GS", 1)) > 0.01:
        print("  FAIL scheme bite differs >0.01 across engines")
        ok = False
    else:
        print("  ok scheme bite within 0.01 across engines")

    # [2] chance origin by position
    print("\n== shooter position mix ==")
    _mix = {}
    for eng in ("QS", "GS"):
        c = Counter(_pos_bucket(p) for (e, o, p, r) in CHANCE_LOG
                    if e == eng)
        tot = sum(c.values()) or 1
        _mix[eng] = {k: v / tot for k, v in c.items()}
        print(f"  {eng}: n={sum(c.values())} " +
              " ".join(f"{k}={v/tot:.2f}" for k, v in sorted(c.items())))
    _dc = abs(_mix.get("QS", {}).get("C", 0) - _mix.get("GS", {}).get("C", 0))
    if _dc > 0.10:
        print(f"  FAIL center share differs {_dc:.2f} > 0.10")
        ok = False
    else:
        print(f"  ok center share within 0.10 ({_dc:.2f})")

    # [3] winger spotlight sanity: wingers get chances on both engines
    for eng in ("QS", "GS"):
        _w = _mix.get(eng, {}).get("W", 0)
        if _w < 0.15:
            print(f"  FAIL {eng} winger chance share {_w:.2f} < 0.15")
            ok = False
    print("  ok winger chance share >= 0.15 both engines"
          if ok else "  (winger check failed above)")

    # [4] wheelhouse vocab normalization (2026-09-30 (c) parity fix):
    # GameSim's raw enum names must resolve to the same grade-location
    # vocabulary quick-sim already used.
    print("\n== wheelhouse location normalization ==")
    _cases = {"high_slot": "slot", "low_slot": "slot",
              "left_circle": "slot", "right_circle": "slot",
              "point": "point", "left_wing": "perimeter",
              "right_wing": "perimeter", "behind_net": "perimeter",
              "crease": "crease", "slot": "slot",
              "netfront": "netfront", "perimeter": "perimeter"}
    _bad = [k for k, v in _cases.items()
            if sc._scheme_norm_location(k) != v]
    if _bad:
        print(f"  FAIL normalization mismatch: {_bad}")
        ok = False
    else:
        print("  ok 12/12 location aliases normalize to grade vocabulary")

    # [5] winger-spotlight scenarios: sane amps, talent-ordered.
    print("\n== spotlight scenario battles ==")
    _centers0 = [p for p in league.teams[0].roster
                 if getattr(getattr(p, "primary_position", None),
                            "name", "") == "CENTER"]
    _shooter = max(_centers0, key=lambda p: float(p.overall_rating()))
    _plug = min(_centers0, key=lambda p: float(p.overall_rating()))
    _goalie = next(p for p in league.teams[1].roster
                   if getattr(getattr(p, "primary_position", None),
                              "name", "") == "GOALIE")
    for _scn in ("d_to_d_onetimer", "netfront_scramble"):
        _a_elite = sc.apply_scenario(0.10, [_shooter], [_goalie], _scn)
        _a_plug = sc.apply_scenario(0.10, [_plug], [_goalie], _scn)
        _sane = (0.85 <= _a_elite / 0.10 <= 1.15
                 and 0.85 <= _a_plug / 0.10 <= 1.15)
        _ordered = _a_elite >= _a_plug
        print(f"  {_scn}: elite_amp={_a_elite/0.10:.4f} "
              f"plug_amp={_a_plug/0.10:.4f} "
              f"sane={_sane} talent_ordered={_ordered}")
        if not (_sane and _ordered):
            print(f"  FAIL {_scn}")
            ok = False
    if ok:
        print("  ok both spotlight scenarios bounded and talent-ordered")

    # [6] spotlight wiring fires end-to-end on both engines (EV one-timers
    # reach the scenario battle; net-front battles fire in GameSim).
    print("\n== spotlight scenario wiring (games) ==")
    for eng in ("QS", "GS"):
        _ot = sum(1 for (e, s) in SCENARIO_LOG
                  if e == eng and s == "d_to_d_onetimer")
        _nf = sum(1 for (e, s) in SCENARIO_LOG
                  if e == eng and s == "netfront_scramble")
        print(f"  {eng}: one-timer battles={_ot} netfront battles={_nf}")
        if _ot == 0:
            print(f"  FAIL {eng} no one-timer scenario battles fired")
            ok = False
    _gs_nf = sum(1 for (e, s) in SCENARIO_LOG
                 if e == "GS" and s == "netfront_scramble")
    if _gs_nf == 0:
        print("  FAIL GS no net-front scenario battles fired")
        ok = False
    if ok:
        print("  ok spotlight battles fire on both engines")

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
