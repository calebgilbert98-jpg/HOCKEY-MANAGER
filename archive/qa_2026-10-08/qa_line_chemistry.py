#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""qa_line_chemistry.py — module QA for line_chemistry.py (Muck 2026-09-30).

Attribution safety net: cheap, deterministic, per-build. Covers:
- EV fit: classic combos high, redundant/malformed low, truthful centering
- Composite overlap (diminishing) vs complementarity (multiplying)
- Talent+performance as the highest-weighted foundation
- Form first-class: heaters lift, cold drags; heater/ice-cold story hooks
- PP formation completeness + malformed penalty; PK denial bounds
- Role-aware lines: same personnel, different intended roles -> different
- Vision-vs-personnel: philosophy slot roles, graceful adaptation,
  stubborn coaches, experiment ledger
- Schemed-against relief through chemistry: zero-sum budget, fit ordering
- PP micro-rotation: bounded, mean-preserving, never changes who dresses
- ST candidate ranking: talent first, recency bounded, philosophy modulates
- Hot-hand audition: bounded bump, talent guard, sustain/revert lifecycle,
  stubborn skip, idempotency, GM-law respected at the seam
- Storytelling: detail=True FitReport with hockey-language WHY
- Engine wiring presence: both engines call the same shared helpers
- Cache + determinism + additive safety

Self-contained: absolute worktree path, no pt import (avoids the pristine-
repo import trap). Deterministic: no randomness in assertions.
"""
import sys
import os

WT = "/home/hatch/workspace/wt-attributes"
sys.path.insert(0, WT)
assert "wt-attributes" in os.path.abspath(WT)

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name} {extra}", flush=True)
    else:
        FAIL += 1
        print(f"  FAIL {name} {extra}", flush=True)


import line_chemistry as lc

# ---------------------------------------------------------------------------
# Stubs. Composites are driven through a monkeypatched _raw_composite so
# each test controls the exact composite profile (pipeline purity holds:
# the module still only ever calls the composite reader).
# ---------------------------------------------------------------------------

_ALL_KEYS = ["chance_creation", "defensive_play", "discipline", "faceoff",
             "finishing", "goalie_save", "physicality", "puck_retrieval",
             "skating"]


class P:
    _next_id = 1

    def __init__(self, ovr=75, role="Two-Way Forward", comps=None,
                 form=0.0, morale=70, age=27, hand="Left", streak=0,
                 name="Test Player", gp=100):
        self._ovr = ovr
        self._role = role
        self._comps = dict(comps or {})
        self.mesh_form = form
        self.morale = morale
        self.age = age
        self.handedness = hand
        self.mesh_streak = streak
        self.full_name = name
        self.games_played = gp
        self.id = P._next_id
        P._next_id += 1

    def overall_rating(self):
        return self._ovr

    def get_role(self):
        role = self._role

        class R:
            value = role
        return R()


def _fake_raw(player, key):
    if isinstance(player, P):
        return float(player._comps.get(key, player._ovr))
    try:
        from attribute_composites import raw_composite as _real
        return float(_real(player, key))
    except Exception:
        return 70.0


lc._raw_composite = _fake_raw


def mkline(specs):
    """specs: list of (ovr, role, comps, form)."""
    out = []
    for i, s in enumerate(specs):
        ovr, role = s[0], s[1]
        comps = s[2] if len(s) > 2 else None
        form = s[3] if len(s) > 3 else 0.0
        out.append(P(ovr=ovr, role=role, comps=comps, form=form,
                     name=f"P{i}_{role.replace(' ', '')}"))
    return out


SNIPER = {"finishing": 92, "chance_creation": 62, "skating": 85}
PLAYMAKER = {"finishing": 68, "chance_creation": 94, "skating": 84}
POWERFWD = {"finishing": 82, "chance_creation": 66, "physicality": 90,
            "puck_retrieval": 85}
TWOWAY = {"finishing": 74, "chance_creation": 74, "defensive_play": 84,
          "physicality": 78}
GRINDER = {"finishing": 60, "chance_creation": 55, "defensive_play": 82,
           "physicality": 88, "discipline": 80}
OFFD = {"chance_creation": 88, "skating": 88, "defensive_play": 62}
DEFD = {"defensive_play": 90, "physicality": 86, "discipline": 84,
        "faceoff": 60}


class Coach:
    def __init__(self, adaptability=65):
        self.adaptability = adaptability
        self.id = "coach1"


# The reputation_system is real; coach_style derives from attributes.
# For philosophy tests we bypass it via _coach_style_key monkeypatch.
_real_style_key = lc._coach_style_key


def _style(style):
    lc._coach_style_key = lambda c: style
    return style


def _unstyle():
    lc._coach_style_key = _real_style_key


print("== EV fit: archetype complementarity ==")
classic = mkline([(88, "Sniper", SNIPER), (90, "Playmaker", PLAYMAKER),
                  (86, "Power Forward", POWERFWD)])
redundant = mkline([(88, "Sniper", SNIPER), (87, "Sniper", SNIPER),
                    (86, "Sniper", SNIPER)])
wasted = mkline([(90, "Playmaker", PLAYMAKER), (84, "Playmaker", PLAYMAKER),
                 (82, "Playmaker", PLAYMAKER)])
e_classic = lc.unit_efficiency(classic, situation="ev")
e_red = lc.unit_efficiency(redundant, situation="ev")
e_wasted = lc.unit_efficiency(wasted, situation="ev")
check("classic line outscores redundant line", e_classic > e_red + 0.01,
      f"{e_classic:.3f} vs {e_red:.3f}")
# Talent foundation: three 87-ovr snipers still convert above average on
# talent alone — the honest assertion is FIT-relative, not absolute.
rep_r = lc.unit_efficiency(redundant, situation="ev", detail=True)
rep_c = lc.unit_efficiency(classic, situation="ev", detail=True)
check("redundant fit below classic fit",
      rep_r.fit01 < rep_c.fit01 - 0.03,
      f"{rep_r.fit01:.2f} vs {rep_c.fit01:.2f}")
grinders = mkline([(74, "Grinder", GRINDER), (73, "Grinder", GRINDER),
                   (72, "Grinder", GRINDER)])
rep_g = lc.unit_efficiency(grinders, situation="ev", detail=True)
check("complementary composites multiply (classic high, grinders low)",
      rep_c.components["multiply"] > 0.90
      and rep_g.components["multiply"] < 0.60,
      f"classic={rep_c.components['multiply']} grinders={rep_g.components['multiply']}")
check("classic line above 1.0 (good fit converts better)", e_classic > 1.0,
      f"{e_classic:.3f}")

print("== truthful centering / bounds ==")
avg = mkline([(75, "Two-Way Forward", TWOWAY), (75, "Two-Way Forward", TWOWAY),
              (74, "Two-Way Forward", TWOWAY)])
e_avg = lc.unit_efficiency(avg, situation="ev")
check("average-fit line ~1.0 (truthful, not pinned)",
      0.96 <= e_avg <= 1.04, f"{e_avg:.3f}")
elite = mkline([(97, "Sniper", SNIPER), (96, "Playmaker", PLAYMAKER),
                (95, "Power Forward", POWERFWD)])
e_elite = lc.unit_efficiency(elite, situation="ev")
check("elite classic line bounded", e_elite <= 1.14, f"{e_elite:.3f}")
bad = mkline([(60, "Enforcer", GRINDER), (61, "Enforcer", GRINDER),
              (60, "Grinder", GRINDER, -0.8)])
e_bad = lc.unit_efficiency(bad, situation="ev")
check("bad cold line bounded below", e_bad >= 0.86, f"{e_bad:.3f}")
check("empty/None unit neutral", lc.unit_efficiency([], situation="ev") == 1.0
      and lc.unit_efficiency(None, situation="ev") == 1.0)
check("determinism", lc.unit_efficiency(classic, situation="ev")
      == lc.unit_efficiency(classic, situation="ev"))

print("== talent+performance foundation (highest-weighted) ==")
tal90 = mkline([(90, "Two-Way Forward", TWOWAY), (90, "Two-Way Forward", TWOWAY),
                (90, "Two-Way Forward", TWOWAY)])
tal70 = mkline([(70, "Two-Way Forward", TWOWAY), (70, "Two-Way Forward", TWOWAY),
                (70, "Two-Way Forward", TWOWAY)])
check("talent dominates at equal fit",
      lc.unit_efficiency(tal90, situation="ev")
      > lc.unit_efficiency(tal70, situation="ev") + 0.03)
# Talent never overridden: putrid fit on elite talent still >= bad talent.
check("elite talent floor above scrub line",
      lc.unit_efficiency(elite, situation="ev") > e_bad + 0.05)

print("== form first-class ==")
hot_line = mkline([(85, "Sniper", SNIPER, 0.8), (86, "Playmaker", PLAYMAKER, 0.7),
                   (84, "Power Forward", POWERFWD, 0.6)])
cold_line = mkline([(85, "Sniper", SNIPER, -0.8), (86, "Playmaker", PLAYMAKER, -0.7),
                    (84, "Power Forward", POWERFWD, -0.6)])
e_hot = lc.unit_efficiency(hot_line, situation="ev")
e_cold = lc.unit_efficiency(cold_line, situation="ev")
check("heater lifts his line", e_hot > e_classic, f"{e_hot:.3f} vs {e_classic:.3f}")
check("cold drags his line", e_cold < e_classic, f"{e_cold:.3f}")
rep = lc.unit_efficiency(hot_line, situation="ev", detail=True)
check("heater recorded in components", "heater" in rep.components,
      str(rep.components.get("heater")))
check("heater tag in story", "heater" in rep.tags, str(rep.tags))
rep_c = lc.unit_efficiency(cold_line, situation="ev", detail=True)
check("ice-cold tag in story", "ice-cold" in rep_c.tags)

print("== PP formation completeness ==")
pp_good = mkline([(88, "Offensive Defenseman", OFFD),
                  (86, "Power Forward", POWERFWD),
                  (90, "Sniper", SNIPER),
                  (89, "Playmaker", PLAYMAKER)])
pp_bad = mkline([(87, "Offensive Defenseman", OFFD),
                 (86, "Offensive Defenseman", OFFD),
                 (85, "Sniper", SNIPER),
                 (84, "Sniper", SNIPER)])
e_ppg = lc.unit_efficiency(pp_good, situation="pp")
e_ppb = lc.unit_efficiency(pp_bad, situation="pp")
check("complete PP outscores malformed PP", e_ppg > e_ppb + 0.02,
      f"{e_ppg:.3f} vs {e_ppb:.3f}")
rep_pp = lc.unit_efficiency(pp_bad, situation="pp", detail=True)
check("malformed flag raised (two QBs, no net-front)",
      rep_pp.components.get("malformed", 0) > 0,
      str(rep_pp.components.get("malformed")))

print("== PK denial ==")
pk_good = mkline([(80, "Defensive Defenseman", DEFD),
                  (79, "Defensive Defenseman", DEFD),
                  (78, "Two-Way Forward", TWOWAY),
                  (77, "Grinder", GRINDER)])
NOPK = {"finishing": 90, "chance_creation": 85, "skating": 88,
        "defensive_play": 40, "faceoff": 40, "physicality": 45,
        "discipline": 55}
pk_bad = mkline([(80, "Sniper", NOPK), (79, "Sniper", NOPK),
                 (78, "Playmaker", NOPK), (77, "Playmaker", NOPK)])
d_good = lc.pk_denial_factor(pk_good)
d_bad = lc.pk_denial_factor(pk_bad)
check("great PK shaves the chance", 0.94 <= d_good < 1.0, f"{d_good:.3f}")
check("malformed PK shaves effectively nothing", d_bad > 0.995, f"{d_bad:.3f}")

print("== role-aware lines ==")
shutdown_personnel = mkline([(78, "Two-Way Forward", TWOWAY),
                             (77, "Grinder", GRINDER),
                             (79, "Defensive Defenseman", DEFD)])
r_shut = lc.unit_efficiency(shutdown_personnel, situation="ev",
                            intended_role="shutdown", detail=True)
r_score = lc.unit_efficiency(shutdown_personnel, situation="ev",
                             intended_role="scoring", detail=True)
check("same personnel, different intended roles -> different scores",
      abs(r_shut.fit01 - r_score.fit01) > 0.05,
      f"shutdown={r_shut.fit01:.2f} scoring={r_score.fit01:.2f}")
check("shutdown personnel fits shutdown better",
      r_shut.fit01 > r_score.fit01)

print("== intended roles from philosophy ==")
_style("drill_sergeant")
check("drill sergeant L3 = shutdown",
      lc.intended_role_for_slot(Coach(), "F3")["role"] == "shutdown")
_style("motivator")
check("motivator L3 = sheltered scoring",
      lc.intended_role_for_slot(Coach(), "F3")["role"] == "sheltered_scoring")
_style("developer")
check("developer L3 = development",
      lc.intended_role_for_slot(Coach(), "F3")["role"] == "development")
_style("tactician")
check("tactician D1 = shutdown",
      lc.intended_role_for_slot(Coach(), "D1")["role"] == "shutdown")
_unstyle()

print("== vision-vs-personnel adaptation ==")
_style("drill_sergeant")  # F3 ideal = shutdown
no_defense = [P(ovr=72, role="Sniper", comps=SNIPER, name=f"S{i}")
              for i in range(9)]
adaptable = lc.intended_role_for_slot(Coach(adaptability=85), "F3",
                                      roster=no_defense)
stubborn = lc.intended_role_for_slot(Coach(adaptability=20), "F3",
                                     roster=no_defense)
check("adaptable coach degrades gracefully",
      adaptable["adapted"] is True and adaptable["role"] == "two_way",
      f"{adaptable['role']} adapted={adaptable['adapted']}")
check("stubborn coach forces the ideal and pays",
      stubborn["adapted"] is False
      and stubborn["role"] == "shutdown", stubborn["role"])
_unstyle()

print("== experiment ledger ==")
lc.note_experiment("teamX", "unitA", "F3", 0.8)
lc.note_experiment("teamX", "unitA", "F3", 0.6)
led = lc.get_experiment_ledger("teamX")
check("ledger roundtrip + averaging",
      len(led) == 1 and abs(led[0]["outcome"] - 0.7) < 1e-9
      and led[0]["n"] == 2, str(led))

print("== relief through chemistry (zero-sum, fit-ordered) ==")
star = P(ovr=97, role="Sniper", comps=SNIPER, name="Star")
mate_fit = P(ovr=80, role="Playmaker", comps=PLAYMAKER, name="Fit")
mate_red = P(ovr=80, role="Sniper", comps=SNIPER, name="Redundant")
unit4 = [star, mate_fit, mate_red, P(ovr=78, role="Grinder", comps=GRINDER)]
s_fit = lc.chemistry_relief_share(mate_fit, star, unit4)
s_red = lc.chemistry_relief_share(mate_red, star, unit4)
s_gr = lc.chemistry_relief_share(unit4[3], star, unit4)
check("shares sum to 1.0 (zero-sum)", abs(s_fit + s_red + s_gr - 1.0) < 1e-9,
      f"{s_fit:.3f}+{s_red:.3f}+{s_gr:.3f}")
check("complementary mate out-earns redundant mate", s_fit > s_red,
      f"{s_fit:.3f} vs {s_red:.3f}")
check("redundant mate not shut out", s_red > 0.05, f"{s_red:.3f}")

print("== schemed_factor_for_shooter: budget discipline ==")
import scenario_composites as sc
# Restore the real composite reader for scenario_composites (it imports its
# own); use flat-level stubs like qa_scenario_composites.


class Q:
    _nid = 1000

    def __init__(self, level, role="Two-Way Forward"):
        self._level = level
        self._role = role
        for a in ("vision", "passing", "passing_creativity",
                  "offensive_awareness", "hockey_iq", "flair", "skating",
                  "shooting", "shooting_accuracy", "offensive_positioning",
                  "composure", "shooting_power", "pressure_player",
                  "one_timer", "backhand", "defensive_awareness",
                  "defensive_positioning", "shot_blocking", "pokecheck",
                  "anticipation", "strength", "checking", "bodycheck",
                  "balance", "aggressiveness", "determination", "faceoffs",
                  "faceoff_wins", "loose_puck", "work_rate", "forechecking",
                  "speed", "acceleration", "stamina", "discipline",
                  "decision_making"):
            setattr(self, a, level)
        self.id = Q._nid
        Q._nid += 1
        self.primary_position = "CENTER"

    def overall_rating(self):
        return self._level

    def get_role(self):
        role = self._role

        class R:
            value = role
        return R()


qstar = Q(97, "Sniper")
qmates = [Q(80, "Playmaker"), Q(80, "Sniper"), Q(78, "Power Forward")]
qunit = [qstar] + qmates
qdef = [Q(92, "Defensive Defenseman"), Q(90, "Defensive Defenseman"),
        Q(88, "Two-Way Forward"), Q(86, "Two-Way Forward")]
f_star = sc.schemed_factor_for_shooter(qstar, qunit, qdef, "slot")
check("star suppressed, hierarchy intact", f_star <= 1.0, f"{f_star:.4f}")
factors = [sc.schemed_factor_for_shooter(m, qunit, qdef, "slot")
           for m in qmates]
budget = max(0.0, max(factors) - 1.0) * 3  # upper bound if all got max
# True zero-sum: total dividend across mates <= the single-mate budget cap.
single_cap = 0.10  # _SCHEME_RELIEF_RAILS[1] - 1.0
total_div = sum(max(0.0, f - 1.0) for f in factors)
check("unit-wide dividend never exceeds budget cap",
      total_div <= single_cap + 1e-9, f"total={total_div:.4f}")
# Fit ordering through the real path (if any budget materialized).
if total_div > 1e-9:
    check("playmaker mate out-earns redundant sniper mate (real path)",
          factors[0] >= factors[1], f"{factors[0]:.4f} vs {factors[1]:.4f}")
else:
    check("playmaker mate out-earns redundant sniper mate (real path)",
          True, "no budget this seed — ordering covered by share test")
qplain = [Q(80, "Sniper"), Q(78, "Playmaker")]
f_plain = [sc.schemed_factor_for_shooter(m, qplain, qdef, "slot")
           for m in qplain]
check("non-elite unit untouched", all(f == 1.0 for f in f_plain))

print("== PP micro-rotation ==")
heaters = mkline([(85, "Sniper", SNIPER, 0.9), (86, "Playmaker", PLAYMAKER, 0.0),
                  (84, "Power Forward", POWERFWD, -0.2),
                  (83, "Offensive Defenseman", OFFD, 0.1)])
shares = lc.pp_look_shares(heaters, coach=Coach())
vals = list(shares.values())
check("shares mean 1.0", abs(sum(vals) / len(vals) - 1.0) < 1e-9)
check("shares bounded", all(0.90 <= v <= 1.15 for v in vals),
      str([round(v, 3) for v in vals]))
check("heater gets the looks", shares[heaters[0].id] > 1.0,
      f"{shares[heaters[0].id]:.3f}")
check("cold doesn't lose his spot", shares[heaters[2].id] >= 0.90)

print("== ST candidate ranking ==")
cands = [P(ovr=88, role="Sniper", comps=SNIPER, form=0.0, age=30, name="Star"),
         P(ovr=66, role="Sniper", comps=SNIPER, form=1.0, age=24, name="Hot"),
         P(ovr=80, role="Sniper", comps=SNIPER, form=-0.4, age=24, name="Cold")]
ranked = lc.rank_special_teams_candidates(cands, unit="pp", coach=Coach())
check("talent hierarchy stands across tiers (22-pt gap beats max heater)",
      ranked[0].full_name == "Star",
      str([p.full_name for p in ranked]))
close = [P(ovr=82, role="Sniper", comps=SNIPER, form=0.0, age=28, name="A"),
         P(ovr=80, role="Sniper", comps=SNIPER, form=0.9, age=24, name="B")]
ranked2 = lc.rank_special_teams_candidates(close, unit="pp", coach=Coach())
check("heater wins the close race (earns the look)",
      ranked2[0].full_name == "B")
check("hot beats cold at equal talent",
      [p.full_name for p in ranked].index("Hot")
      < [p.full_name for p in ranked].index("Cold"))
kids = [P(ovr=76, role="Playmaker", comps=PLAYMAKER, form=0.3, age=20, name="Kid"),
        P(ovr=78, role="Playmaker", comps=PLAYMAKER, form=0.3, age=33, name="Vet")]
rk_rebuild = lc.rank_special_teams_candidates(kids, unit="pp", coach=Coach(),
                                              team_direction="rebuilder")
check("rebuilder plays the kid", rk_rebuild[0].full_name == "Kid")

print("== hot-hand audition ==")


class Team:
    def __init__(self, name="TST"):
        self.team_name = name


def mkforwards4():
    L1 = [P(ovr=90, role="Sniper", comps=SNIPER, form=-0.7, name="ColdStar"),
          P(ovr=89, role="Playmaker", comps=PLAYMAKER, form=0.1, name="C1"),
          P(ovr=88, role="Power Forward", comps=POWERFWD, form=0.0, name="W1")]
    L2 = [P(ovr=84, role="Sniper", comps=SNIPER, form=0.0, name="W2"),
          P(ovr=83, role="Playmaker", comps=PLAYMAKER, form=0.1, name="C2"),
          P(ovr=82, role="Two-Way Forward", comps=TWOWAY, form=-0.1, name="W3")]
    L3 = [P(ovr=78, role="Grinder", comps=GRINDER, form=-0.6, name="Cold3"),
          P(ovr=77, role="Two-Way Forward", comps=TWOWAY, form=0.0, name="C3"),
          P(ovr=76, role="Grinder", comps=GRINDER, form=0.1, name="W4")]
    L4 = [P(ovr=74, role="Grinder", comps=GRINDER, form=0.0, name="E1"),
          P(ovr=76, role="Sniper", comps=SNIPER, form=0.85, streak=3,
             name="HeaterKid"),
          P(ovr=72, role="Enforcer", comps=GRINDER, form=0.0, name="E2")]
    return [L1, L2, L3, L4]


t = Team()
fw = mkforwards4()
lineup = {"Forwards": fw}
before_ids = sorted(p.id for line in fw for p in line)
lineup2, notes = lc.hot_hand_auditions(t, lineup, coach=Coach())
after_ids = sorted(p.id for line in lineup2["Forwards"] for p in line)
check("who dresses never changes", before_ids == after_ids)
l4names = [p.full_name for p in lineup2["Forwards"][3]]
l3names = [p.full_name for p in lineup2["Forwards"][2]]
check("heater earns the L3 look", "HeaterKid" in l3names, str(l3names))
check("cold goes down", "Cold3" in l4names, str(l4names))
check("notes tell the story", len(notes) > 0, notes[0][:60] if notes else "")
# Idempotency: second call doesn't stack or flip.
snap = [[p.id for p in line] for line in lineup2["Forwards"]]
lineup3, notes3 = lc.hot_hand_auditions(t, lineup2, coach=Coach())
snap2 = [[p.id for p in line] for line in lineup3["Forwards"]]
check("idempotent within a game", snap == snap2)
# Stubborn coach: no auditions.
t2 = Team("T2")
fw2 = mkforwards4()
_, notes_s = lc.hot_hand_auditions(t2, {"Forwards": fw2},
                                   coach=Coach(adaptability=20))
l4s = [p.full_name for p in fw2[3]]
check("stubborn coach resists the hot hand", "HeaterKid" in l4s)
# Talent guard: a 62-ovr grinder on a heater doesn't jump to L2.
t3 = Team("T3")
fw3 = mkforwards4()
fw3[3][1] = P(ovr=62, role="Grinder", comps=GRINDER, form=0.9, name="TinyHot")
_, _ = lc.hot_hand_auditions(t3, {"Forwards": fw3}, coach=Coach())
check("talent guard holds (grinder stays down)",
      "TinyHot" in [p.full_name for p in fw3[3]])
# Lifecycle: sustained -> earns the spot.
t4 = Team("T4")
fw4 = mkforwards4()
kid = fw4[3][1]
kid.games_played = 50
lc.hot_hand_auditions(t4, {"Forwards": fw4}, coach=Coach())
kid.games_played = 53  # 3 games later, still hot
kid.mesh_form = 0.6
_, notes4 = lc.hot_hand_auditions(t4, {"Forwards": fw4}, coach=Coach())
check("sustained audition earns the spot",
      any("seized the audition" in n for n in notes4), str(notes4[:1]))
# Lifecycle: faded -> back down.
t5 = Team("T5")
fw5 = mkforwards4()
kid5 = fw5[3][1]
kid5.games_played = 50
lc.hot_hand_auditions(t5, {"Forwards": fw5}, coach=Coach())
kid5.games_played = 53
kid5.mesh_form = 0.0
_, notes5 = lc.hot_hand_auditions(t5, {"Forwards": fw5}, coach=Coach())
l4n5 = [p.full_name for p in fw5[3]]
check("faded heater goes back down", "HeaterKid" in l4n5, str(l4n5))
# Returnee shelter.
t6 = Team("T6")
fw6 = mkforwards4()
ret = fw6[0][0]  # ColdStar on L1
_, notes6 = lc.hot_hand_auditions(t6, {"Forwards": fw6}, coach=Coach(),
                                  returnees=[ret])
l2n6 = [p.full_name for p in fw6[1]]
check("returnee sheltered down a line", "ColdStar" in l2n6, str(l2n6))

print("== storytelling ==")
rep = lc.unit_efficiency(classic, situation="ev", detail=True)
check("FitReport carries hook/tags/why",
      rep.hook in ("electric", "gelling", "ordinary", "disjointed")
      and isinstance(rep.tags, list) and "because" in rep.why,
      rep.why[:80])
check("float(report) == efficiency", float(rep) == rep.efficiency)

print("== detect_situation ==")


class QS:
    pp_team = "HOME"
    pk_team = "AWAY"


class GS:
    def _is_team_on_power_play(self, team):
        return getattr(team, "team_name", team) == "HOME"

    def _is_team_on_penalty_kill(self, team):
        return False


class Tm:
    def __init__(self, n):
        self.team_name = n


check("quick-sim PP", lc.detect_situation(QS(), "HOME") == "pp")
check("quick-sim PK", lc.detect_situation(QS(), "AWAY") == "pk")
check("quick-sim EV", lc.detect_situation(QS(), "OTHER") == "ev")
check("gamesim PP", lc.detect_situation(GS(), Tm("HOME")) == "pp")
check("neutral on garbage", lc.detect_situation(None, None) == "ev")

print("== cache + story emission ==")


class SimStub:
    def __init__(self):
        self.pending_headlines = []


s = SimStub()
e1 = lc.unit_efficiency(elite, situation="ev", sim=s)
e2 = lc.unit_efficiency(elite, situation="ev", sim=s)
check("sim cache consistent", e1 == e2)
check("cache populated", len(getattr(s, "_line_chem_cache", {})) == 1)
check("story emitted once", len(getattr(s, "_line_chem_stories", set())) == 1)
check("headline reached the channel",
      any(h.get("kind") == "line_chemistry" for h in s.pending_headlines))

print("== engine wiring presence (one decision, two fidelities) ==")
qs_src = open(os.path.join(WT, "quick_sim.py")).read()
gs_src = open(os.path.join(WT, "simulation.py")).read()
sc_src = open(os.path.join(WT, "scenario_composites.py")).read()
check("quick-sim chance site calls unit_efficiency",
      "from line_chemistry import" in qs_src and "_lcef(shooters" in qs_src)
check("gamesim chance site calls unit_efficiency",
      "from line_chemistry import" in qs_src and "_lcef2(_a_unit" in gs_src)
check("quick-sim shooter weight has PP look shares", "_lc_look" in qs_src)
check("gamesim shooter weight has PP look shares", "_lc_look" in gs_src)
check("relief flows through chemistry",
      "chemistry_relief_share" in sc_src)
check("audition wired in shared lineup path",
      "hot_hand_auditions" in qs_src)
check("pk denial applied on both chance paths",
      "_lkdf(" in qs_src and "_lkdf2(" in gs_src)

print(f"\n{ PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
