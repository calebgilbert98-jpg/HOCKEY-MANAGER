# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: Analytics integration (2026-10-01).

Verifies the new-systems analytics wiring (additive-only):
1. Grade-A/B/C chance records surface in the analytics hub (xG by grade).
2. quick_sim feeds the hub (shot-level records with grade/context).
3. advanced_metrics ixg_grade from grade data (ground truth).
4. Chance context (scenario/composite) recorded on shot records.
5. Awards races surface ixg_grade / grade_a_share.
6. Scouting value signals use grade ground truth.

Deterministic: seeded RNG. Each section independent.
"""
import random
import sys

sys.path.insert(0, "/home/hatch/workspace/HOCKEY-MANAGER")

passed, failed = [], []


def check(label, cond, detail=""):
    (passed if cond else failed).append(label)
    if not cond:
        print(f"  FAIL: {label}" + (f" -- {detail}" if detail else ""))


def make_teams():
    import game_classes as g
    from game_classes import PlayerPosition
    t1 = g.Team("Hub HC", "HHC", "Div", "Conf")
    t2 = g.Team("Rivals", "RIV", "Div", "Conf")
    for i in range(14):
        for t in (t1, t2):
            t.roster.append(g.Player(
                first_name=f"P{i}", last_name="X", age=25,
                primary_position=PlayerPosition.CENTER,
                jersey_number=i + 1))
    return t1, t2


# 1: mesh_system grade_xg_value -------------------------------------------
print("== 1: grade xG canonical values ==")
from mesh_system import grade_xg_value, CHANCE_GRADE_XG_VALUE
check("A=0.14", grade_xg_value("A") == 0.14, grade_xg_value("A"))
check("B=0.08", grade_xg_value("B") == 0.08, grade_xg_value("B"))
check("C=0.05", grade_xg_value("C") == 0.05, grade_xg_value("C"))
check("unknown falls back to B", grade_xg_value("Z") == 0.08)
check("None falls back to B", grade_xg_value(None) == 0.08)

# 2: roll_chance_grade context_out ----------------------------------------
print("== 2: chance context capture ==")
from mesh_system import roll_chance_grade
_ctx = {}
_g = roll_chance_grade("breakaway", 0.1, context_out=_ctx)
check("breakaway grades A", _g == "A", _g)
check("context has hard_gate", _ctx.get("hard_gate") == "breakaway_or_rebound",
      _ctx.get("hard_gate"))
check("context has location", _ctx.get("location") == "breakaway")
_ctx2 = {}
_g2 = roll_chance_grade("slot", 0.5,
                        situation={"quick_release": True},
                        game_ctx={"clutch": True, "is_playoff": True},
                        context_out=_ctx2)
check("context captures situation", _ctx2.get("situation", {}).get("quick_release") is True,
      _ctx2.get("situation"))
check("context captures game_ctx clutch", _ctx2.get("game_ctx", {}).get("clutch") is True)
check("context captures playoff", _ctx2.get("game_ctx", {}).get("is_playoff") is True)
# No context_out = old behavior exactly
_g3 = roll_chance_grade("slot", 0.5)
check("no context_out still grades", _g3 in ("A", "B", "C"), _g3)

# 3: GameSim shot records have grade + context -----------------------------
print("== 3: GameSim analytics records ==")
random.seed(7)
t1, t2 = make_teams()
from simulation import GameSim
sim = GameSim(t1, t2)
sim.simulate_game()
shots = sim.shot_log
check("shots recorded", len(shots) > 20, len(shots))
_have_grade = [s for s in shots if s.get("grade") in ("A", "B", "C")]
check("shots have grade A/B/C", len(_have_grade) > 0,
      f"{len(_have_grade)}/{len(shots)}")
_have_ctx = [s for s in shots if isinstance(s.get("chance_context"), dict)]
check("shots have chance_context dict", len(_have_ctx) > 0,
      f"{len(_have_ctx)}/{len(shots)}")
# At least some contexts should have meaningful content
_rich = [s for s in _have_ctx if s["chance_context"].get("location")]
check("context has location", len(_rich) > 0)

# 4: hub grade breakdown ---------------------------------------------------
print("== 4: hub grade xG aggregation ==")
# analytics_hub builds a tkinter view at import; stub customtkinter so the
# pure aggregation functions are testable headless.
import types as _t
_ctk = _t.ModuleType("customtkinter")
_ctk.CTkFrame = type("CTkFrame", (), {})
sys.modules["customtkinter"] = _ctk
import analytics_hub as ah
rec = t1.analytics_games[0]
hshots = rec["shots"]
grows = ah.grade_xg_rows(hshots)
check("grade rows returned", len(grows) > 0)
check("grade rows have conv", all("conv" in r for r in grows))
check("grade rows sorted A,B,C",
      [r["grade"] for r in grows if r["grade"] in "ABC"] ==
      sorted([r["grade"] for r in grows if r["grade"] in "ABC"],
             key=lambda g: "ABC".index(g)))
_total_xg = sum(r["xg"] for r in grows)
_txg, _tg = ah.team_xg(hshots)
check("grade xG sums to team xG", abs(_total_xg - _txg) < 0.01,
      f"{_total_xg} vs {_txg}")
pgrows = ah.player_grade_xg_rows(hshots)
check("player grade rows returned", len(pgrows) > 0)
check("player grade rows have a_share", all("a_share" in r for r in pgrows))

# 5: quick_sim feeds the hub -----------------------------------------------
print("== 5: quick_sim analytics feed ==")
random.seed(11)
q1, q2 = make_teams()
from quick_sim import AdvancedGameSim as QuickSim
qs = QuickSim(q1, q2)
qs.run()
check("quick_sim persisted analytics_games", len(getattr(q1, "analytics_games", [])) >= 1)
qrec = q1.analytics_games[-1]
check("quick_sim record has shots", len(qrec.get("shots", [])) > 0,
      len(qrec.get("shots", [])))
_qg = [s for s in qrec["shots"] if s.get("grade") in ("A", "B", "C")]
check("quick_sim shots graded", len(_qg) > 0, f"{len(_qg)}")
_qc = [s for s in qrec["shots"] if isinstance(s.get("chance_context"), dict)]
check("quick_sim shots have context", len(_qc) > 0)
check("quick_sim record tagged", qrec.get("engine") == "quick_sim")
# Hub reads quick_sim records the same way
_qgrows = ah.grade_xg_rows(qrec["shots"])
check("hub aggregates quick_sim grades", len(_qgrows) > 0)

# 6: advanced_metrics ixg_grade --------------------------------------------
print("== 6: grade-based ixG ==")
import advanced_metrics as am
from types import SimpleNamespace


def _mk_player(ga, gb, gc, goals=5, shots=100, gp=30):
    st = SimpleNamespace(goals=goals, shots=shots, assists=10,
                         games_played=gp, hits=20, blocked_shots=15,
                         penalty_minutes=10,
                         grade_a_shots=ga, grade_b_shots=gb,
                         grade_c_shots=gc)
    p = SimpleNamespace(stats=st, shooting=70, playmaking=65,
                        passing=65, puck_handling=60, skating=70,
                        defensive_awareness=55, strength=60,
                        offensive_instincts=65, morale=70, age=27,
                        goals=goals, assists=10, games_played=gp,
                        shots=shots,
                        grade_a_shots=ga, grade_b_shots=gb,
                        grade_c_shots=gc)
    return p


p1 = _mk_player(20, 50, 30)  # 20*0.14 + 50*0.08 + 30*0.05 = 2.8+4+1.5=8.3
m1 = am.skater_advanced(p1)
check("ixg_grade computed", abs(m1.ixg_grade - 8.3) < 0.01, m1.ixg_grade)
check("grade_a_shots stored", m1.grade_a_shots == 20)
check("grade_a_share", abs(m1.grade_a_share - 0.20) < 0.001, m1.grade_a_share)
check("modeled ixg untouched", m1.ixg > 0, m1.ixg)
p0 = _mk_player(0, 0, 0)
m0 = am.skater_advanced(p0)
check("no grade data -> ixg_grade 0", m0.ixg_grade == 0.0)
check("no grade data -> a_share 0", m0.grade_a_share == 0.0)

# 7: awards surface grade data ----------------------------------------------
print("== 7: awards visibility ==")
import awards_race as aw


def _mk_award_player(pid, goals, assists, gp=30):
    st = SimpleNamespace(goals=goals, assists=assists, games_played=gp,
                         shots=100, hits=10, blocked_shots=5,
                         penalty_minutes=4, grade_a_shots=15,
                         grade_b_shots=40, grade_c_shots=20)
    return SimpleNamespace(id=pid, stats=st, goals=goals, team_name="HHC",
                           shooting=70, playmaking=65, passing=65,
                           puck_handling=60, skating=70,
                           defensive_awareness=55, strength=60,
                           offensive_instincts=65, morale=70, age=27,
                           primary_position="C")


_aps = [_mk_award_player(1, 30, 40), _mk_award_player(2, 25, 35)]
_hart = aw.hart_race(_aps, {"HHC": 0.6})
check("hart has ixg_grade", all("ixg_grade" in r for r in _hart),
      [r.get("ixg_grade") for r in _hart])
check("hart has grade_a_share", all("grade_a_share" in r for r in _hart))
check("hart still sorted by score",
      _hart[0]["score"] >= _hart[1]["score"])
_ross = aw.art_ross_race(_aps)
check("ross has ixg_grade", all("ixg_grade" in r for r in _ross))
_rocket = aw.rocket_race(_aps)
check("rocket has ixg_grade", all("ixg_grade" in r for r in _rocket))

# 8: scouting ground-truth signals ------------------------------------------
print("== 8: scouting shot-quality signals ==")
import analytics_scouting as asc
# Player with big grade-ixG gap: 20A/50B/30C -> 8.3 ixg_grade, 0 goals
_sp = _mk_player(20, 50, 30, goals=0, gp=30)
_score, _sigs, _risks = asc._skater_value_signals(_sp, 0.5)
_has_quality_sig = any("grade-ixG" in s or "High-danger" in s for s in _sigs)
check("scouting emits grade-based signal", _has_quality_sig, _sigs)
# Elite A-share player
_sp2 = _mk_player(30, 50, 20, goals=10, gp=30)  # 30% A share
_score2, _sigs2, _ = asc._skater_value_signals(_sp2, 0.5)
_has_ashare = any("High-danger driver" in s for s in _sigs2)
check("scouting emits A-share signal", _has_ashare, _sigs2)

# ---------------------------------------------------------------------------
print(f"\n{len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILURES:", failed)
    sys.exit(1)
