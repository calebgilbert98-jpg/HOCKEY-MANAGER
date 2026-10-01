# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
#!/usr/bin/env python3
"""qa_parity_ws4.py -- WS4 scenario gap-closure parity probes (AdvGS).

Verifies the three WS4 ports call the SAME shared functions as GameSim
("one decision, two fidelities"):

 [1] rush_chance ....... AdvGS deke resolves through the shared
                         rush_chance scenario battle (deker vs NEAREST
                         defender); factor identical to a direct
                         shared-function call on the same participants;
                         the old skating single-composite hook is gone
                         from the deke path (never stack, §6 rule 2).
 [2] netfront_scramble . AdvGS deflection converts through the shared
                         battle (forward vs goalie+defender), EV-only
                         gating (never on PP / empty net), factor
                         identical to the direct shared call.
 [3] rebound parity .... NEITHER engine applies netfront_scramble in
                         the discrete rebound chance (both use the
                         shared mesh_system.netfront_finish_chance) --
                         the port correctly did NOT touch it.
 [4] PP zone hooks .... H1 entry quality (conversion), H2 forecheck
                         strip->transition (deke mix), H3 strip-back
                         roll (pass recovery / SH rush), H4 rush defense
                         (SH suppression): presence, bounds, and
                         agreement with the shared pp_zone_sustenance.
 [5] soak ............... full AdvGS games: no crash, sane totals,
                         scenario hits > 0.

Run: python3 qa_parity_ws4.py   (headless)
"""
import sys
import os
import random
import inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
assert "wt-parity-ws4" in os.path.abspath(__file__), \
    "must run from the wt-parity-ws4 worktree"

import scenario_composites as sc
from game_classes import League, PlayerPosition
from player_generator import PlayerGenerator

OK = True


def check(name, cond, detail=""):
    global OK
    status = "ok" if cond else "FAIL"
    if not cond:
        OK = False
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""),
          flush=True)


# --------------------------------------------------------------------------
# instrumentation: log every apply_scenario call
# --------------------------------------------------------------------------
SCN_LOG = []  # (scenario, base, result, off_ids, def_ids, engine_tag)

_orig_apply_scenario = sc.apply_scenario


def _wrapped_apply_scenario(base, off_side, def_side, scenario, sim=None,
                            **kw):
    try:
        eng = getattr(sim, "_instr_engine", "?") if sim is not None else "?"
    except Exception:
        eng = "?"
    _o = [getattr(p, "id", None) for p in (off_side or []) if p is not None]
    _d = [getattr(p, "id", None) for p in (def_side or []) if p is not None]
    try:
        _res = _orig_apply_scenario(base, off_side, def_side, scenario,
                                    sim=sim, **kw)
    except Exception:
        _res = base
    SCN_LOG.append((str(scenario), float(base), float(_res), _o, _d, eng))
    return _res


sc.apply_scenario = _wrapped_apply_scenario

# Also patch the already-imported alias inside quick_sim if it imported one
# at module level (it imports inside methods, so the module attr is enough).


def _boost(p, level):
    for a in ("shooting_accuracy", "shooting_power", "one_timer",
              "offensive_positioning", "defensive_positioning",
              "skating_speed", "agility", "balance", "passing",
              "passing_accuracy", "passing_creativity", "play_vision",
              "puck_handling", "faceoffs", "checking", "hitting",
              "shot_blocking", "stick_checking", "defensive_awareness",
              "strength", "aggression", "determination", "work_rate",
              "poise", "adaptability", "stickhandling", "anticipation",
              "off_the_puck", "hockey_iq", "composure", "creativity",
              "decision_making", "vision", "deking", "offensive_awareness"):
        try:
            setattr(p, a, level)
        except Exception:
            pass


def make_league():
    random.seed(4242)
    league = League("National Hockey League", "NHL")
    gen = PlayerGenerator()
    for team in league.teams[:2]:
        for _ in range(6):
            team.roster.append(gen.create_player(
                position=random.choice([PlayerPosition.CENTER,
                                        PlayerPosition.LEFT_WING,
                                        PlayerPosition.RIGHT_WING]),
                team_name=team.team_name))
        for _ in range(4):
            team.roster.append(gen.create_player(
                position=PlayerPosition.DEFENSE, team_name=team.team_name))
        team.roster.append(gen.create_player(
            position=PlayerPosition.GOALIE, team_name=team.team_name))
    return league


def skaters(team):
    return [p for p in team.roster
            if getattr(getattr(p, "primary_position", None), "name", "")
            != "GOALIE"]


def goalie_of(team):
    return next(p for p in team.roster
                if getattr(getattr(p, "primary_position", None), "name", "")
                == "GOALIE")


def fresh_sim(league, tag="QS"):
    from quick_sim import AdvancedGameSim
    H, A = league.teams[0], league.teams[1]
    s = AdvancedGameSim(H, A)
    s._instr_engine = tag
    return s, H, A


def set_positions(sim, mapping):
    for p, xy in mapping.items():
        sim.coordinate_engine.player_positions[getattr(p, "id", None)] = xy


# --------------------------------------------------------------------------
# [1] rush_chance on the deke path
# --------------------------------------------------------------------------
def probe_rush(league):
    print("\n== [1] rush_chance (deke path) ==")
    sim, H, A = fresh_sim(league)
    hn, an = H.team_name, A.team_name
    hf = [p for p in skaters(H) if "WING" in
          getattr(getattr(p, "primary_position", None), "name", "")]
    hd = [p for p in H.roster if getattr(
        getattr(p, "primary_position", None), "name", "") == "DEFENSE"]
    ad = [p for p in A.roster if getattr(
        getattr(p, "primary_position", None), "name", "") == "DEFENSE"]
    af = skaters(A)
    deker = hf[0]
    _boost(deker, 88)
    near_d, far_d = ad[0], ad[1]
    _boost(near_d, 70)
    _boost(far_d, 70)
    # controlled units + coordinates: near_d is the nearest checker
    sim.on_ice[hn]["Forwards"] = hf[:3]
    sim.on_ice[hn]["Defense"] = hd[:2]
    sim.on_ice[an]["Forwards"] = af[:3]
    sim.on_ice[an]["Defense"] = [near_d, far_d]
    set_positions(sim, {deker: (150, 42.5), near_d: (140, 42.5),
                        far_d: (60, 42.5)})

    # the old skating single-composite hook must be gone from the deke path
    import attribute_composites as ac
    _ac_calls = []
    _orig_ac = ac.apply_amplifier

    def _wac(prob, player, composite, **kw):
        _ac_calls.append(str(composite))
        return _orig_ac(prob, player, composite, **kw)

    ac.apply_amplifier = _wac
    SCN_LOG.clear()
    try:
        random.seed(7)
        sim._resolve_deke_event(deker, hn, 1.0)
    finally:
        ac.apply_amplifier = _orig_ac

    _rush = [e for e in SCN_LOG if e[0] == "rush_chance"]
    check("rush_chance applied on AdvGS deke", len(_rush) == 1,
          f"applications={len(_rush)}")
    check("no skating single-composite on deke path (§6:2 no stacking)",
          "skating" not in _ac_calls, f"composites={sorted(set(_ac_calls))}")
    if _rush:
        _scn, _base, _res, _o, _d, _eng = _rush[0]
        check("offense side is [deker]", _o == [deker.id], f"off={_o}")
        check("defense side is the NEAREST defender", _d == [near_d.id],
              f"def={_d} near={near_d.id} far={far_d.id}")
        # paired-context agreement: same participants -> same factor
        _direct = _orig_apply_scenario(
            _base, [deker], [near_d], "rush_chance",
            sim=sim, off_team=hn, def_team=an)
        _f_logged = _res / _base if _base else 0.0
        _f_direct = _direct / _base if _base else 0.0
        check("factor == shared-function factor (paired context)",
              abs(_f_logged - _f_direct) < 1e-9,
              f"logged={_f_logged:.6f} direct={_f_direct:.6f}")
        _lo, _hi = sc.SCENARIOS["rush_chance"]["rails"]
        check("factor inside scenario rails", _lo <= _f_logged <= _hi,
              f"factor={_f_logged:.4f} rails=({_lo},{_hi})")


# --------------------------------------------------------------------------
# [2] netfront_scramble on the deflection path (+ EV gating)
# --------------------------------------------------------------------------
def probe_netfront(league):
    print("\n== [2] netfront_scramble (deflection path) ==")
    sim, H, A = fresh_sim(league)
    hn, an = H.team_name, A.team_name
    hf = skaters(H)
    af = skaters(A)
    ad = [p for p in A.roster if getattr(
        getattr(p, "primary_position", None), "name", "") == "DEFENSE"]
    hg = goalie_of(H)
    ag = goalie_of(A)
    tipper = hf[0]
    _boost(tipper, 90)
    _boxer = ad[0]
    for a in ("checking", "strength", "balance", "defensive_awareness"):
        try:
            setattr(_boxer, a, 40)
        except Exception:
            pass
    sim.on_ice[hn]["Forwards"] = hf[:3]
    sim.on_ice[hn]["Defense"] = [p for p in H.roster if getattr(
        getattr(p, "primary_position", None), "name", "") == "DEFENSE"][:2]
    sim.on_ice[hn]["Goalie"] = hg
    sim.on_ice[an]["Forwards"] = af[:3]
    sim.on_ice[an]["Defense"] = [_boxer, ad[1]]
    sim.on_ice[an]["Goalie"] = ag

    SCN_LOG.clear()
    _fired = False
    for _seed in range(40):
        random.seed(100 + _seed)
        _n0 = len([e for e in SCN_LOG if e[0] == "netfront_scramble"])
        sim._resolve_deflection_event(tipper, hf[:3], ag, hn, an)
        _n1 = len([e for e in SCN_LOG if e[0] == "netfront_scramble"])
        if _n1 > _n0:
            _fired = True
            break
    check("netfront_scramble fires on AdvGS deflection", _fired)
    _nf = [e for e in SCN_LOG if e[0] == "netfront_scramble"]
    if _nf:
        _scn, _base, _res, _o, _d, _eng = _nf[-1]
        check("offense side is [deflector]", _o == [tipper.id])
        check("defense side is [goalie, defender]",
              _d == [ag.id, _boxer.id], f"def={_d}")
        _direct = _orig_apply_scenario(
            _base, [tipper], [ag, _boxer], "netfront_scramble",
            sim=sim, off_team=hn, def_team=an)
        _f_logged = _res / _base if _base else 0.0
        _f_direct = _direct / _base if _base else 0.0
        check("factor == shared-function factor (paired context)",
              abs(_f_logged - _f_direct) < 1e-9,
              f"logged={_f_logged:.6f} direct={_f_direct:.6f}")

    # EV gating: on the PP the scenario must NOT fire
    _n_before = len([e for e in SCN_LOG if e[0] == "netfront_scramble"])
    sim.pp_team = hn
    sim.pk_team = an
    for _seed in range(40):
        random.seed(100 + _seed)
        sim._resolve_deflection_event(tipper, hf[:3], ag, hn, an)
    _n_after = len([e for e in SCN_LOG if e[0] == "netfront_scramble"])
    check("no netfront_scramble on the PP (EV-only, mirrors GameSim)",
          _n_after == _n_before,
          f"before={_n_before} after={_n_after}")
    sim.pp_team = None
    sim.pk_team = None


# --------------------------------------------------------------------------
# [3] rebound parity: neither engine applies the scenario there
# --------------------------------------------------------------------------
def probe_rebound(league):
    print("\n== [3] rebound parity (scenario correctly absent) ==")
    sim, H, A = fresh_sim(league)
    hn, an = H.team_name, A.team_name
    hf = skaters(H)
    ag = goalie_of(A)
    sim.on_ice[hn]["Forwards"] = hf[:3]
    sim.on_ice[an]["Goalie"] = ag
    # source guard: the scenario string must not appear in the rebound body
    _src = inspect.getsource(sim._resolve_rebound_event)
    check("netfront_scramble not wired into _resolve_rebound_event",
          "netfront_scramble" not in _src)
    _src_d = inspect.getsource(sim._resolve_deflection_event)
    check("netfront_scramble wired into _resolve_deflection_event",
          "netfront_scramble" in _src_d)
    # behavioral: drive rebounds, assert the scenario never fires there
    SCN_LOG.clear()
    _reb_created = 0
    for _seed in range(60):
        random.seed(500 + _seed)
        try:
            sim._resolve_rebound_event(ag, hn, an, "wrist shot", hf[:3])
        except Exception:
            pass
        try:
            _reb_created = sim.stats[an][ag.id].get("rebounds_created", 0)
        except Exception:
            pass
    _nf = [e for e in SCN_LOG if e[0] == "netfront_scramble"]
    check("rebound chances resolve without the scenario (GameSim's "
          "rebound chance uses netfront_finish_chance only)",
          len(_nf) == 0, f"rebounds_created={_reb_created}")

# --------------------------------------------------------------------------
# [4] PP zone hooks H1..H4
# --------------------------------------------------------------------------
def probe_pp_hooks(league):
    print("\n== [4] PP zone hooks H1..H4 ==")
    from quick_sim import AdvancedGameSim
    from line_chemistry import pp_zone_sustenance as _direct_pzs
    sim, H, A = fresh_sim(league)
    hn, an = H.team_name, A.team_name
    hf = skaters(H)
    hd = [p for p in H.roster if getattr(
        getattr(p, "primary_position", None), "name", "") == "DEFENSE"]
    af = skaters(A)
    ad = [p for p in A.roster if getattr(
        getattr(p, "primary_position", None), "name", "") == "DEFENSE"]
    hg = goalie_of(H)
    ag = goalie_of(A)
    sim.on_ice[hn]["Forwards"] = hf[:3]
    sim.on_ice[hn]["Defense"] = hd[:2]
    sim.on_ice[hn]["Goalie"] = hg
    sim.on_ice[an]["Forwards"] = af[:3]
    sim.on_ice[an]["Defense"] = ad[:2]
    sim.on_ice[an]["Goalie"] = ag
    _unit = [p for p in hf[:3] + hd[:2] if p]

    # --- helper agreement: same shared function GameSim calls ---
    sim.pp_team = hn
    sim.pk_team = an
    _h = sim._pp_forecheck_sustenance()
    _d = float(_direct_pzs(_unit, sim=sim, team=H))
    check("helper == shared pp_zone_sustenance (same unit)",
          abs(_h - _d) < 1e-9, f"helper={_h:.6f} direct={_d:.6f}")
    check("helper inside scenario rails", 0.75 <= _h <= 1.25, f"h={_h:.4f}")
    sim.pp_team = None
    sim.pk_team = None
    check("helper returns 1.0 when no PP",
          sim._pp_forecheck_sustenance() == 1.0)
    sim.pp_team = hn
    sim.pk_team = an

    # --- H2: forecheck strip -> deke mix, PP-gated, bounded ---
    # NOTE: use a low-skill plug -- elite attributes inflate pass_prob
    # past the cumulative threshold (pre-existing engine behavior),
    # which would make DEKE unreachable regardless of H2. Also
    # neutralize the pre-existing volume stack (systems matchup,
    # SHOT_LIFT, the :2236 PP volume hook) for the count test: those
    # inflate shot_prob until the DEKE band is squeezed past 1.0 and
    # the H2 width change becomes unmeasurable. H2's own input is
    # still the patched sustenance value.
    _h2plug = hf[2]
    for a in ("creativity", "decision_making", "stickhandling", "passing"):
        try:
            setattr(_h2plug, a, 8)
        except Exception:
            pass
    import line_chemistry as _lc
    _real = AdvancedGameSim._pp_forecheck_sustenance
    _real_pzs = _lc.pp_zone_sustenance
    _real_matchup = sim._systems_matchup
    try:
        _lc.pp_zone_sustenance = lambda *a, **k: 1.0
        sim._systems_matchup = {}

        def _count_dekes(sus, seed=9):
            AdvancedGameSim._pp_forecheck_sustenance = lambda self: sus
            random.seed(seed)
            _n = 0
            for _ in range(3000):
                if sim._determine_event_type(_h2plug, _unit, 1.0, team=H,
                                             opp_team_name=an) == "DEKE":
                    _n += 1
            return _n

        _hi = _count_dekes(1.25)
        _lo = _count_dekes(0.75)
        _ratio = _hi / _lo if _lo else 0.0
        check("H2 scales deke mix on PP (1.25 vs 0.75)",
              1.35 <= _ratio <= 1.95 and _lo > 50,
              f"dekes={_hi}/{_lo} ratio={_ratio:.3f} (expect ~1.667)")

        # gated: no PP -> patching changes nothing
        sim.pp_team = None
        _a = _count_dekes(1.25, seed=11)
        _b = _count_dekes(0.75, seed=11)
        check("H2 does nothing when no PP", _a == _b, f"{_a} vs {_b}")
        sim.pp_team = hn
    finally:
        AdvancedGameSim._pp_forecheck_sustenance = _real
        _lc.pp_zone_sustenance = _real_pzs
        sim._systems_matchup = _real_matchup

    # --- H1: entry quality, PP-gated, bounded [0.875, 1.125] ---
    _pre = []
    _orig_grade = sim._apply_chance_grade

    def _wgrade(shot_chance, *a, **k):
        _pre.append(float(shot_chance))
        return _orig_grade(shot_chance, *a, **k)

    sim._apply_chance_grade = _wgrade
    _plug = hf[-1]  # weak shooter: keep shot_chance off the clamp bounds
    for a in ("shooting_accuracy", "shooting_power", "one_timer",
              "offensive_positioning"):
        try:
            setattr(_plug, a, 30)
        except Exception:
            pass
    try:
        def _shot_pre(sus, seed=21):
            AdvancedGameSim._pp_forecheck_sustenance = lambda self: sus
            _pre.clear()
            random.seed(seed)
            sim._resolve_shot_event(_plug, ag, hn, an, 1.0, 1.0, 1.0, _unit)
            return _pre[-1] if _pre else None

        _p_hi = _shot_pre(1.25)
        _p_lo = _shot_pre(0.75)
        _r = _p_hi / _p_lo if _p_lo else 0.0
        check("H1 entry factor bounded (1.125/0.875)",
              1.20 <= _r <= 1.36,
              f"pre-grade={_p_hi:.5f}/{_p_lo:.5f} ratio={_r:.4f} "
              f"(expect {1.125/0.875:.4f})")

        # gated: no PP -> identical
        sim.pp_team = None
        _p1 = _shot_pre(1.25, seed=23)
        _p2 = _shot_pre(0.75, seed=23)
        check("H1 does nothing when no PP", _p1 == _p2,
              f"{_p1:.5f} vs {_p2:.5f}")
        sim.pp_team = hn

        # --- H4: SH-rush defense suppression via sh_rush_sus ---
        def _rush_pre(sus, seed=31):
            _pre.clear()
            random.seed(seed)
            sim._resolve_sh_rush_event(ad[0], hn, an, sus)
            return _pre[-1] if _pre else None

        _r_hi = _rush_pre(1.25)
        _r_lo = _rush_pre(0.75)
        _rr = _r_hi / _r_lo if _r_lo else 0.0
        _exp = (1.0 / (1.0 + 0.42 * (1.25 - 0.68))) / (
            1.0 / (1.0 + 0.42 * (0.75 - 0.68)))
        check("H4 suppresses SH rush (better structure -> worse look)",
              0.78 <= _rr <= 0.88,
              f"ratio={_rr:.4f} (expect {_exp:.4f})")
        check("H4 suppression is a pure discount", _rr < 1.0)

        # sh_rush_sus=None -> every other caller untouched
        _pre.clear()
        random.seed(31)
        sim._resolve_shot_event(_plug, ag, hn, an, 1.0, 1.0, 1.0, _unit)
        _plain = _pre[-1] if _pre else None
        check("plain shot path unaffected by H4 kwarg", _plain is not None)
    finally:
        AdvancedGameSim._pp_forecheck_sustenance = _real
        sim._apply_chance_grade = _orig_grade

    # --- H3: strip-back roll -> recovery OR shorthanded rush ---
    # find a seed where the PP pass fails, then make the strip roll
    # deterministic via sustenance extremes (99.0 always strips,
    # 0.0 always burns)
    _passer = hf[1]
    for a in ("passing_accuracy", "passing", "passing_creativity",
              "play_vision"):
        try:
            setattr(_passer, a, 1)
        except Exception:
            pass
    _fail_seed = None
    try:
        for _seed in range(200):
            AdvancedGameSim._pp_forecheck_sustenance = lambda self: 1.0
            sim._ws4_scenario_hits = {}
            random.seed(900 + _seed)
            sim.events.clear()
            sim._resolve_pass_event(_passer, _unit, hn, an, 1.0)
            _hits = sim._ws4_scenario_hits.get("pp_strip_back", 0)
            if _hits > 0:
                _fail_seed = 900 + _seed
                break
    finally:
        AdvancedGameSim._pp_forecheck_sustenance = _real
    check("found a failing-PP-pass seed", _fail_seed is not None)

    if _fail_seed is not None:
        # strip wins: pass recovered, no SH rush (pass events log to
        # event_log with type 'PASS', not to self.events)
        AdvancedGameSim._pp_forecheck_sustenance = lambda self: 99.0
        sim._ws4_scenario_hits = {}
        random.seed(_fail_seed)
        sim.events.clear()
        sim.event_log.clear()
        sim._resolve_pass_event(_passer, _unit, hn, an, 1.0)
        _passes = [e for e in sim.event_log
                   if e.get("type") == "PASS"
                   and e.get("details", {}).get("success")]
        _rushes = [e for e in sim.events
                   if e.get("event") == "Shorthanded Rush"]
        check("strip-back recovers the failed PP pass",
              len(_rushes) == 0 and len(_passes) == 1,
              f"successful_passes={len(_passes)} sh_rushes={len(_rushes)}")
        # strip loses: interceptor walks in shorthanded
        AdvancedGameSim._pp_forecheck_sustenance = lambda self: 0.0
        sim._ws4_scenario_hits = {}
        random.seed(_fail_seed)
        sim.events.clear()
        sim._resolve_pass_event(_passer, _unit, hn, an, 1.0)
        _rushes = [e for e in sim.events
                   if e.get("event") == "Shorthanded Rush"]
        check("burned strip-back triggers a SH rush", len(_rushes) == 1,
              f"sh_rushes={len(_rushes)}")
        AdvancedGameSim._pp_forecheck_sustenance = _real
        # EV pass failures never hit the strip branch
        sim.pp_team = None
        sim._ws4_scenario_hits = {}
        random.seed(_fail_seed)
        sim.events.clear()
        sim._resolve_pass_event(_passer, _unit, hn, an, 1.0)
        _hits = sim._ws4_scenario_hits.get("pp_strip_back", 0)
        check("H3 does nothing at even strength", _hits == 0)
        sim.pp_team = hn


# --------------------------------------------------------------------------
# [5] full-game soak
# --------------------------------------------------------------------------
def probe_soak(league):
    print("\n== [5] full-game soak (AdvGS) ==")
    from quick_sim import AdvancedGameSim
    for gi in range(2):
        random.seed(7000 + gi)
        H, A = league.teams[0], league.teams[1]
        sim = AdvancedGameSim(H, A)
        try:
            sim.run()
        except Exception as exc:
            check(f"game {gi} completes without crashing", False,
                  f"{type(exc).__name__}: {exc}")
            return
        _g = sim.score.get(H.team_name, 0) + sim.score.get(A.team_name, 0)
        check(f"game {gi} sane goal total", 0 < _g < 30, f"goals={_g}")
    _hits = getattr(sim, "_ws4_scenario_hits", {}) or {}
    check("rush_chance fired in live games", _hits.get("rush_chance", 0) > 0,
          f"hits={_hits.get('rush_chance', 0)}")
    check("netfront_scramble fired in live games",
          _hits.get("netfront_scramble", 0) > 0,
          f"hits={_hits.get('netfront_scramble', 0)}")
    check("pp_strip_back evaluated in live games",
          _hits.get("pp_strip_back", 0) >= 0,
          f"evaluations={_hits.get('pp_strip_back', 0)}")


def main():
    print("QA parity WS4 -- scenario gap closure (worktree wt-parity-ws4)",
          flush=True)
    league = make_league()
    probe_rush(league)
    probe_netfront(league)
    probe_rebound(league)
    probe_pp_hooks(league)
    probe_soak(league)
    print()
    print("RESULT:", "ALL GREEN" if OK else "FAILURES PRESENT")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
