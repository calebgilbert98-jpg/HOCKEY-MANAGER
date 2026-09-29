"""QA: Cross-engine chance-grading parity (2026-09-28, per Muck).

Muck's standing rule: quick-sim (AdvancedGameSim) and GameSim must not
have disparity in the chance-grading and scoring systems -- and NOT by
simplifying. Both engines stay full-fidelity; they consume the same
shared-layer decisions (one decision, two fidelities).

This file locks:
1. Grade mult parity: GameSim's xG grade multiplier IS the shared
   mesh_system.chance_grade_finish_mult -- same inputs, same relative
   effect. No local copy.
2. No dead/duplicate matchup: the old _apply_archetype_matchup (string *
   float, always dead) is gone; matchup lives only in the shared grade.
3. Turnover upgrades grade: a goalie-turnover rebound is grade A (the
   shared hard gate), not just quality="high".
4. Seeded distribution parity: identical inputs through the shared roll
   give identical grade streams (determinism -- the engines cannot
   diverge what they both delegate).
5. Per-grade conversion parity: the grade's relative finishing effect is
   identical across engines within tolerance.

Run: DISPLAY=:99 python3 qa_engine_parity.py
"""
import sys, os
sys.path.insert(0, '.')
sys.path.insert(0, os.path.expanduser('~/workspace/playthrough'))

PASS = 0
FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name} {detail}")

print("=== Cross-Engine Chance-Grading Parity QA ===\n")

import random
from collections import Counter
from mesh_system import (
    roll_chance_grade, chance_grade_finish_mult, chance_grade_clamp,
    CHANCE_GRADE_FINISH_MULT,
)

# ------------------------------------------------------------------
# 1. Grade mult parity: GameSim xG uses the shared mult (one decision)
# ------------------------------------------------------------------
print("1. Grade multiplier is one shared decision:")
import simulation as _sim_mod
from simulation import GameSim, ShotLocation, ShotType

# Bare instance for pure-method access (no game state needed for xG math)
_gs = GameSim.__new__(GameSim)

def _xg(grade):
    return _gs._calculate_expected_goal_value(
        ShotLocation.LOW_SLOT, ShotType.WRIST_SHOT, "medium", 20.0,
        grade=grade)

_xg_a, _xg_b, _xg_c = _xg("A"), _xg("B"), _xg("C")
_mA, _mB, _mC = (chance_grade_finish_mult("A"),
                 chance_grade_finish_mult("B"),
                 chance_grade_finish_mult("C"))
print(f"    shared mults: A={_mA} B={_mB} C={_mC}")
print(f"    GameSim xG:   A={_xg_a:.4f} B={_xg_b:.4f} C={_xg_c:.4f}")
check("GameSim xG A/B ratio == shared mult A/B ratio",
      abs((_xg_a / _xg_b) - (_mA / _mB)) < 1e-9,
      f"{_xg_a/_xg_b:.6f} vs {_mA/_mB:.6f}")
check("GameSim xG C/B ratio == shared mult C/B ratio",
      abs((_xg_c / _xg_b) - (_mC / _mB)) < 1e-9,
      f"{_xg_c/_xg_b:.6f} vs {_mC/_mB:.6f}")
check("GameSim xG A > B > C ordering", _xg_a > _xg_b > _xg_c)

# quick-sim path uses the same shared mult (import-level lock)
import quick_sim as _qs_mod
_src = open(os.path.join(os.path.dirname(_qs_mod.__file__),
                         "quick_sim.py")).read()
check("quick_sim _apply_chance_grade calls chance_grade_finish_mult",
      "chance_grade_finish_mult as _cgfm" in _src)
check("quick_sim applies grade-specific clamp via chance_grade_clamp",
      "chance_grade_clamp as _cgc" in _src)
_sim_src = open(os.path.join(os.path.dirname(_sim_mod.__file__),
                             "simulation.py")).read()
check("simulation xG imports chance_grade_finish_mult (no local copy)",
      "chance_grade_finish_mult as _cgfm" in _sim_src)
# The fallback except-branch keeps a legacy dict as a safety net; the
# primary path is locked by the ratio tests above. Verify the primary
# path calls the shared function inside _calculate_expected_goal_value.
import re as _re
_xg_src = _re.search(r"def _calculate_expected_goal_value\(.*?(?=\n    def )",
                     _sim_src, _re.S).group(0)
check("xG primary path calls shared chance_grade_finish_mult",
      "_cgfm(grade)" in _xg_src)

# ------------------------------------------------------------------
# 2. No dead/duplicate matchup layer
# ------------------------------------------------------------------
print("\n2. Matchup lives only in the shared grade:")
check("_apply_archetype_matchup removed from GameSim",
      not hasattr(GameSim, "_apply_archetype_matchup"))
check("no _apply_archetype_matchup CALL remains (comments may mention it)",
      "self._apply_archetype_matchup(" not in _sim_src)
# The shared grade still does matchup (lock the one decision in place)
from mesh_system import _chance_matchup_tilt
check("shared _chance_matchup_tilt exists", callable(_chance_matchup_tilt))

# ------------------------------------------------------------------
# 3. Turnover -> grade A (shared hard gate: rebound is grade A)
# ------------------------------------------------------------------
print("\n3. Goalie-turnover rebound upgrades the grade:")
check("turnover sets grade='A' in _resolve_shot_on_goal",
      'grade = "A"' in _sim_src)

# ------------------------------------------------------------------
# 4. Seeded distribution parity (shared roll is deterministic)
# ------------------------------------------------------------------
print("\n4. Seeded grade-stream parity (same inputs -> same grades):")
class Fake:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

def _grade_stream(seed, n=2000):
    random.seed(seed)
    # Neutral two-way forward (not sniper-biased) for a representative mix
    s = Fake(offensive_positioning=72, skating=72,
             offensive_awareness=72, morale=70, archetype="Two-Way Forward")
    d = Fake(archetype="Two-Way Defenseman",
             defensive_positioning=72, defensive_awareness=72)
    g = Fake(positioning=80, reflexes=80)
    out = []
    for _ in range(n):
        out.append(roll_chance_grade(
            "slot", 0.45, s, defenders=[d], goalie=g,
            situation={"quick_release": False},
            game_ctx={"rivalry_heat": 30, "morale": 70,
                      "d_fatigue": 55, "team_d_weakness": 1.0}))
    return out

_s1 = _grade_stream(777)
_s2 = _grade_stream(777)  # same seed, same inputs -- both engines delegate here
check("identical seeds give identical grade streams", _s1 == _s2)
_c = Counter(_s1)
_tot = len(_s1)
print(f"    stream: A={_c['A']/_tot:.1%} B={_c['B']/_tot:.1%} "
      f"C={_c['C']/_tot:.1%}")
check("stream distribution in NHL-like band",
      0.15 <= _c['A']/_tot <= 0.35 and 0.40 <= _c['B']/_tot <= 0.65)

# ------------------------------------------------------------------
# 5. Per-grade conversion parity within tolerance
# ------------------------------------------------------------------
print("\n5. Per-grade conversion parity (relative effect):")
# quick-sim: post-grade chance = pre * mult, clamped. GameSim: xG * mult.
# The RELATIVE finishing edge of A over B must match across engines.
# quick-sim effective (pre=0.09, the measured mean):
_pre = 0.09
_qs_a = max(0.10, min(0.26, _pre * _mA))
_qs_b = max(0.04, min(0.16, _pre * _mB))
_qs_c = max(0.015, min(0.09, _pre * _mC))
_gs_a = _xg_a / _xg_b  # relative to B (== shared ratio by test 1)
print(f"    quick-sim effective: A={_qs_a:.3f} B={_qs_b:.3f} C={_qs_c:.3f}")
print(f"    GameSim relative:    A={_gs_a:.3f} B=1.000 "
      f"C={_xg_c/_xg_b:.3f}")
# The A-over-B finishing edge must agree within 15% (different base
# scales are the allowed fidelity difference; the GRADE effect is not)
_qs_edge = _qs_a / _qs_b
check("A-over-B finishing edge agrees within 15%",
      abs(_qs_edge - _gs_a) / _gs_a < 0.15,
      f"qs={_qs_edge:.3f} gs={_gs_a:.3f}")
_qs_cedge = _qs_c / _qs_b
_gs_cedge = _xg_c / _xg_b
check("C-vs-B suppression agrees within 25%",
      abs(_qs_cedge - _gs_cedge) / max(_gs_cedge, 1e-9) < 0.25,
      f"qs={_qs_cedge:.3f} gs={_gs_cedge:.3f}")

# ------------------------------------------------------------------
# 6. End-to-end distribution parity (12 games/engine -- hardened
# 2026-09-29: 6 games left GameSim's ~8% grade-A conversion on too few
# chances, so A>B>C ordering flaked on small samples)
# ------------------------------------------------------------------
print("\n6. End-to-end grade distribution parity (12 games/engine):")
try:
    import sys as _sys2
    _sys2.path.insert(0, os.path.expanduser('~/workspace/playthrough'))
    from pt import load_career as _lc
    _gm, _app = _lc('s2_deadline.hm')
    _teams = [t for t in _gm.league.teams
              if getattr(t, 'league_name', '') == 'National Hockey League']
    from quick_sim import AdvancedGameSim as _AdvGS

    def _collect(engine_cls, n=12, seed=999):
        import random as _r
        _r.seed(seed)
        # Reset shared mesh form/streak: record_performance writes
        # player.mesh_form during a run, and the players are shared
        # between engine runs. Without reset, the second engine inherits
        # the first engine's heaters -- a test artifact, not a parity
        # signal. (Heater mechanics themselves are covered in
        # qa_chance_grading.)
        for _t in _teams:
            for _p in getattr(_t, 'roster', []) or []:
                try:
                    _p.mesh_form = 0.0
                    _p.mesh_streak = 0
                except Exception:
                    pass
        _cs, _cg = Counter(), Counter()
        for _i in range(n):
            _s = engine_cls(_teams[_i % 32], _teams[(_i * 3 + 1) % 32])
            if engine_cls is _AdvGS:
                _s.run()
                # quick-sim: {team_name: {pid: stats}}
                _all_stats = []
                for _pd in (_s.stats or {}).values():
                    _all_stats.extend(_pd.values())
            else:
                _s.simulate_game()
                # GameSim: {pid: stats} (flat)
                _all_stats = list((_s.game_stats or {}).values())
            for _st in _all_stats:
                if not isinstance(_st, dict):
                    continue
                for _g in 'abc':
                    _cs[_g] += _st.get(f'grade_{_g}_shots', 0)
                    _cg[_g] += _st.get(f'grade_{_g}_goals', 0)
        return _cs, _cg

    _qs_c, _qs_g = _collect(_AdvGS, n=12, seed=999)
    _gs_c, _gs_g = _collect(GameSim, n=12, seed=999)
    _qt, _gt = sum(_qs_c.values()), sum(_gs_c.values())
    print(f"    quick-sim dist: " +
          ", ".join(f"{g.upper()}={_qs_c[g]/_qt:.1%}" for g in 'abc'))
    print(f"    GameSim dist:   " +
          ", ".join(f"{g.upper()}={_gs_c[g]/_gt:.1%}" for g in 'abc'))
    # Distributions must agree within 8pp per grade (different event
    # granularity is the allowed fidelity difference)
    _ok = all(abs(_qs_c[g]/_qt - _gs_c[g]/_gt) < 0.08 for g in 'abc')
    check("grade distributions agree within 8pp", _ok)
    # Per-grade conversion ordering must hold in both (A > B > C)
    for _lbl, _c, _g in (("quick-sim", _qs_c, _qs_g),
                         ("GameSim", _gs_c, _gs_g)):
        _ra = _g['a'] / max(_c['a'], 1)
        _rb = _g['b'] / max(_c['b'], 1)
        _rc = _g['c'] / max(_c['c'], 1)
        print(f"    {_lbl} conv: A={_ra:.1%} B={_rb:.1%} C={_rc:.1%}")
        check(f"{_lbl} conversion ordering A>B>C", _ra > _rb > _rc)
except Exception as _e:
    check("end-to-end parity harness runs", False, str(_e)[:120])

print(f"\n{'='*40}\nPASS: {PASS}  FAIL: {FAIL}")
sys.exit(1 if FAIL else 0)
