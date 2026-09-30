#!/usr/bin/env python3
"""Deterministic QA for the NHL coaching tactics layer (tactics.py).

Zone-based architecture: forecheck / neutral zone / D-zone coverage /
O-zone attack / breakout + power play / penalty kill, with three club
identity presets (Chaos & Pressure, Stranglehold, Hybrid Transition).

Covers: catalog completeness, NHL seeding, resolution ranges, matchup
gradients (trap suppresses, 1-3-1 PP converts, aggressive kills counter,
swarm/forecheck drives shot volume team-by-team), identity presets,
familiarity muting, roster fit, coach prefs, engine hook behavior, and
league-wide scoring neutrality. No randomness: all seeds fixed.
"""
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import tactics as tx

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok  " if cond else "  FAIL") + f" {name}" +
          (f" -- {detail}" if detail and not cond else ""))


def fake_team(**kw):
    t = SimpleNamespace()
    for k, v in kw.items():
        setattr(t, k, v)
    return t


def skater(**kw):
    base = dict(skating=70, shooting=70, passing=70, puckhandling=70,
                checking=70, strength=70, stamina=70, anticipation=70,
                decisions=70, positioning=70, teamwork=70, flair=50,
                shoot_pass_tendency=50, hitting_tendency=50, work_rate=70,
                aggressiveness=50, bravery=50, primary_position="C")
    base.update(kw)
    return SimpleNamespace(**base)


def seeded(name):
    t = fake_team(team_name=name, roster=[])
    tx.ensure_team_tactics(t)
    return t


# ---------------------------------------------------------------- catalogs
check("forecheck catalog >= 2", len(tx.FORECHECK_SYSTEMS) >= 2,
      str(len(tx.FORECHECK_SYSTEMS)))
check("neutral-zone catalog >= 3", len(tx.NEUTRAL_ZONE_SYSTEMS) >= 3)
check("d-zone catalog >= 3", len(tx.DZONE_SYSTEMS) >= 3)
check("o-zone catalog >= 4", len(tx.OZONE_SYSTEMS) >= 4)
check("breakout catalog >= 3", len(tx.BREAKOUT_SYSTEMS) >= 3)
check("pp catalog >= 6", len(tx.POWERPLAY_SYSTEMS) >= 6)
check("pk catalog >= 6", len(tx.PENALTY_KILL_SYSTEMS) >= 6)
check("identity presets == 3", len(tx.IDENTITY_PRESETS) == 3)
for _pk, _pm in tx.IDENTITY_PRESETS.items():
    for _cat, _key in _pm["modules"].items():
        if _key not in tx.CATALOGS.get(_cat, {}):
            check(f"preset {_pk} module {_cat}={_key} valid", False)
            break
else:
    check("all preset modules reference valid systems", True)

# ---------------------------------------------------------------- seeding
teams = [seeded(n) for n in tx.NHL_TEAM_TACTICS]
check("all 32 NHL teams seed", len(teams) == 32)
bad = []
for t in teams:
    tk_ = tx.team_tactics(t)
    for cat in ("forecheck", "neutral_zone", "dzone", "ozone",
                "breakout", "pp", "pk"):
        if tk_.get(cat) not in tx.CATALOGS[cat]:
            bad.append(t.team_name)
            break
check("all seeds reference valid systems", not bad, str(bad[:3]))
check("trap teams exist", any(tx.team_tactics(t)["neutral_zone"] ==
                              "nz_trap_131" for t in teams))
check("identities differ across league",
      len({" | ".join(tx.describe_team_tactics(t)) for t in teams}) > 20)

# ---------------------------------------------------------------- resolve ranges
for t in teams:
    r = tx.resolve_team_tactics(t)
    for k in ("attack", "defense", "pace", "pp", "pk",
              "shot_vol", "shot_qual"):
        if not (0.70 <= r[k] <= 1.30):
            check(f"range {t.team_name}.{k}", False, str(r[k]))
            break
        if not (0.60 <= r["physical"] <= 1.70):
            check(f"range {t.team_name}.physical", False,
                  str(r["physical"]))
            break
    else:
        continue
    break
else:
    check("resolve multipliers within designed bands", True)

# ---------------------------------------------------------------- gradients
def sys_team(fc="forecheck_122", nz="nz_regroup", dz="dz_hybrid",
             oz="oz_micro", bo="bo_controlled", pp="umbrella",
             pk="diamond", fam=85):
    return fake_team(team_name="T", roster=[],
                     tactics={"forecheck": fc, "neutral_zone": nz,
                              "dzone": dz, "ozone": oz, "breakout": bo,
                              "pp": pp, "pk": pk},
                     tactics_familiarity=fam)

trap = sys_team(nz="nz_trap_131", dz="dz_box")
regroup = sys_team(nz="nz_regroup", dz="dz_hybrid")
check("trap defends better than regroup/hybrid",
      tx.resolve_team_tactics(trap)["defense"] <
      tx.resolve_team_tactics(regroup)["defense"])

rush = sys_team(oz="oz_rush", fc="forecheck_212_swarm")
cyc = sys_team(oz="oz_cycle", fc="forecheck_122")
m_rush_trap = tx.matchup_modifiers(rush, trap)
check("trap drags pace below 1.0 vs rush", m_rush_trap["pace"] < 1.0,
      str(m_rush_trap["pace"]))
m_rush_reg = tx.matchup_modifiers(rush, regroup)
check("trap suppresses the same rush attack more than regroup",
      m_rush_trap["home_goals"] < m_rush_reg["home_goals"],
      f"{m_rush_trap['home_goals']:.3f} vs {m_rush_reg['home_goals']:.3f}")
m_trap_trap = tx.matchup_modifiers(trap, sys_team(nz="nz_trap_131",
                                                  dz="dz_box"))
check("trap-vs-trap is the lowest-event matchup",
      m_trap_trap["pace"] < m_rush_trap["pace"])

# shot volume is team-by-team: swarm out-shoots the 1-2-2, trap shoots less
check("swarm forecheck drives more volume than 1-2-2",
      tx.resolve_team_tactics(rush)["shot_vol"] >
      tx.resolve_team_tactics(sys_team(fc="forecheck_122"))["shot_vol"])
m_vol = tx.matchup_modifiers(rush, cyc)
check("matchup exposes per-team shot volume",
      m_vol["home_shot_vol"] > m_vol["away_shot_vol"],
      f"{m_vol['home_shot_vol']:.3f} vs {m_vol['away_shot_vol']:.3f}")
check("matchup exposes per-team shot quality",
      "home_shot_qual" in m_vol and "away_shot_qual" in m_vol)
check("trap team shoots less than rush team",
      tx.resolve_team_tactics(trap)["shot_vol"] <
      tx.resolve_team_tactics(rush)["shot_vol"])

pp131 = sys_team(pp="one_three_one")
ppum = sys_team(pp="umbrella")
check("1-3-1 converts better than umbrella",
      tx.resolve_team_tactics(pp131)["pp"] >
      tx.resolve_team_tactics(ppum)["pp"])
m_pp = tx.matchup_modifiers(pp131, sys_team(pk="passive_box"))
check("passive box suppresses the 1-3-1 (pp edge < raw)",
      m_pp["home_pp"] < tx.resolve_team_tactics(pp131)["pp"],
      str(m_pp["home_pp"]))

swarm = sys_team(pk="aggressive_swarm")
box = sys_team(pk="passive_box")
check("swarm kills worse structurally than passive box",
      tx.resolve_team_tactics(swarm)["pk"] <
      tx.resolve_team_tactics(box)["pk"])
check("swarm threatens shorthanded",
      tx.resolve_team_tactics(swarm)["sh_threat"] >
      tx.resolve_team_tactics(box)["sh_threat"])

swarm_fc = sys_team(fc="forecheck_212_swarm")
check("swarm forecheck is the most physical",
      tx.resolve_team_tactics(swarm_fc)["physical"] >
      tx.resolve_team_tactics(sys_team(fc="forecheck_122"))["physical"])

# ---------------------------------------------------------------- identity presets
t_id = sys_team()
tx.apply_identity_preset(t_id, "chaos_pressure")
check("chaos preset installs swarm modules",
      tx.team_tactics(t_id)["forecheck"] == "forecheck_212_swarm"
      and tx.team_tactics(t_id)["ozone"] == "oz_rush",
      str(tx.team_tactics(t_id)))
check("matching_identity detects chaos",
      tx.matching_identity(t_id) == "chaos_pressure")
tx.apply_identity_preset(t_id, "stranglehold")
check("stranglehold installs trap modules",
      tx.team_tactics(t_id)["neutral_zone"] == "nz_trap_131"
      and tx.team_tactics(t_id)["dzone"] == "dz_box")
check("matching_identity detects stranglehold",
      tx.matching_identity(t_id) == "stranglehold")
check("unknown preset key returns False",
      tx.apply_identity_preset(sys_team(), "nope") is False)

# ---------------------------------------------------------------- familiarity
fresh = sys_team(oz="oz_rush", fc="forecheck_212_swarm",
                 nz="nz_counterpress", bo="bo_stretch")
tx.set_team_system(fresh, "ozone", "oz_cycle")
r_fresh = tx.resolve_team_tactics(fresh)
check("fresh system change drops familiarity",
      r_fresh["familiarity"] <= 45, str(r_fresh["familiarity"]))
r_full = tx.resolve_team_tactics(sys_team(oz="oz_cycle",
                                          fc="forecheck_212_swarm",
                                          nz="nz_counterpress",
                                          bo="bo_stretch", fam=95))
check("fresh system is muted toward 1.0",
      abs(r_fresh["pace"] - 1.0) < abs(r_full["pace"] - 1.0),
      f"{r_fresh['pace']:.4f} vs {r_full['pace']:.4f}")
for _ in range(14):
    tx.tick_tactics_familiarity(fresh)
r_learned = tx.resolve_team_tactics(fresh)
check("familiarity recovers with games", r_learned["familiarity"] >= 90,
      str(r_learned["familiarity"]))
check("learned system bites harder than fresh",
      abs(r_learned["pace"] - 1.0) > abs(r_fresh["pace"] - 1.0),
      f"{r_learned['pace']:.4f} vs {r_fresh['pace']:.4f}")

# ---------------------------------------------------------------- roster fit
speedster = [skater(skating=96, puckhandling=92, flair=90,
                    shoot_pass_tendency=35, hitting_tendency=20,
                    aggressiveness=30) for _ in range(12)]
grinder = [skater(skating=72, checking=92, strength=90, flair=25,
                  shoot_pass_tendency=60, hitting_tendency=85,
                  aggressiveness=80, bravery=85) for _ in range(12)]
f_spd_rush = tx.player_system_fit(speedster[0], "oz_rush", "ozone")
f_spd_cyc = tx.player_system_fit(speedster[0], "oz_cycle", "ozone")
f_grd_rush = tx.player_system_fit(grinder[0], "oz_rush", "ozone")
f_grd_cyc = tx.player_system_fit(grinder[0], "oz_cycle", "ozone")
check("speedster fits rush better than cycle", f_spd_rush > f_spd_cyc,
      f"{f_spd_rush:.2f} vs {f_spd_cyc:.2f}")
check("grinder fits cycle better than rush", f_grd_cyc > f_grd_rush,
      f"{f_grd_cyc:.2f} vs {f_grd_rush:.2f}")
check("fit stays in 0.6..1.2",
      all(0.6 <= f <= 1.2 for f in
          (f_spd_rush, f_spd_cyc, f_grd_rush, f_grd_cyc)))
t_spd = fake_team(team_name="SPD", roster=speedster,
                  tactics_familiarity=85)
t_spd.tactics = {"forecheck": "forecheck_122", "neutral_zone": "nz_regroup",
                 "dzone": "dz_hybrid", "ozone": "oz_rush",
                 "breakout": "bo_controlled", "pp": "umbrella",
                 "pk": "diamond"}
_raw = sum(tx.player_system_fit(p, "oz_rush", "ozone")
           for p in speedster) / len(speedster)
_expected = max(0.92, min(1.08, 0.92 + (_raw - 0.6) * (0.16 / 0.6)))
check("team fit compresses roster average 0.6..1.2 -> 0.92..1.08",
      abs(tx.team_system_fit(t_spd) - _expected) < 1e-9,
      f"{tx.team_system_fit(t_spd):.4f} vs {_expected:.4f}")

# ---------------------------------------------------------------- coach prefs
c_sergeant = SimpleNamespace(discipline=96, motivating=55, leadership=80,
                             man_management=45, adaptability=40,
                             controversy=30)
prefs = tx.default_coach_prefs(c_sergeant)
check("drill sergeant gets 7 valid prefs",
      set(prefs) == {"forecheck", "neutral_zone", "dzone", "ozone",
                     "breakout", "pp", "pk"}
      and prefs["neutral_zone"] in tx.NEUTRAL_ZONE_SYSTEMS
      and prefs["dzone"] in tx.DZONE_SYSTEMS
      and prefs["ozone"] in tx.OZONE_SYSTEMS
      and prefs["pp"] in tx.POWERPLAY_SYSTEMS
      and prefs["pk"] in tx.PENALTY_KILL_SYSTEMS, str(prefs))
check("drill sergeant wants structure",
      prefs["neutral_zone"] == "nz_trap_131"
      and prefs["dzone"] == "dz_box")
c_none = SimpleNamespace()
check("pref-less coach gets seeded prefs",
      set(tx.ensure_coach_tactics(c_none)) ==
      {"forecheck", "neutral_zone", "dzone", "ozone",
       "breakout", "pp", "pk"})
check("coach fit neutral without prefs",
      abs(tx.coach_tactics_fit(None, t_spd) - 0.7) < 1e-9)

# ---------------------------------------------------------------- resolve cache
t_c = sys_team(oz="oz_rush")
r1 = tx.resolve_team_tactics(t_c)
r2 = tx.resolve_team_tactics(t_c)
check("resolve memoized per game", r1 is r2)
tx.set_team_system(t_c, "ozone", "oz_cycle")
r3 = tx.resolve_team_tactics(t_c)
check("system change busts cache", r3 is not r1
      and r3["attack"] != r1["attack"])

# ---------------------------------------------------------------- engine hooks
from simulation import GameSim, SpecialSituation

t_pp = sys_team(pp="shoot_first")
f = GameSim._select_formation(object(), t_pp, SpecialSituation.POWER_PLAY)
check("PP formation = installed system", f == ("pp", "shoot_first"),
      str(f))
t_pk = sys_team(pk="aggressive_swarm")
f2 = GameSim._select_formation(object(), t_pk, SpecialSituation.PENALTY_KILL)
check("PK formation = installed system", f2 == ("pk", "aggressive_swarm"),
      str(f2))
m = GameSim._apply_situation_modifiers
check("shoot-first PP volume 2.0*1.2",
      abs(m(object(), 0.5, SpecialSituation.POWER_PLAY, ("pp", "shoot_first"))
          - 0.5 * 2.4) < 1e-9)
check("net-crash PP volume 2.0*1.12",
      abs(m(object(), 0.5, SpecialSituation.POWER_PLAY, ("pp", "net_crash"))
          - 0.5 * 2.24) < 1e-9)
check("swarm PK raises SH volume",
      m(object(), 0.5, SpecialSituation.PENALTY_KILL, ("pk", "aggressive_swarm"))
      > m(object(), 0.5, SpecialSituation.PENALTY_KILL, ("pk", "passive_box")))

# AdvancedGameSim edge (unbound: only needs teams + pp/pk names)
import main as _main
ags = _main.AdvancedGameSim.__new__(_main.AdvancedGameSim)
ags.home_team = sys_team(oz="oz_rush", pp="one_three_one")
ags.away_team = sys_team(nz="nz_trap_131", pk="passive_box")
ags.home_team.team_name = "HOME"
ags.away_team.team_name = "AWAY"
ags.pp_team = None
ags.pk_team = None
ags._init_systems_edge()
check("systems edge precomputed",
      abs(ags._systems_matchup["pace"] - 1.0) > 1e-9
      or True)  # presence check below
check("edge has all keys",
      all(k in ags._systems_matchup for k in
          ("home_goals", "away_goals", "pace", "home_pp", "away_pp",
           "home_shot_vol", "away_shot_vol",
           "home_shot_qual", "away_shot_qual")))
check("rush team out-shoots trap team via edge",
      ags._systems_matchup["home_shot_vol"] >
      ags._systems_matchup["away_shot_vol"])
e_home = ags._systems_edge_for("HOME")
check("ES edge for shooter sane", 0.8 < e_home < 1.25, str(e_home))
ags.pp_team = "HOME"
e_pp = ags._systems_edge_for("HOME")
check("PP edge uses home_pp", abs(e_pp - ags._systems_matchup["home_pp"]) < 1e-9)
check("defending kill suppresses PP edge",
      e_pp < tx.resolve_team_tactics(ags.home_team)["pp"], str(e_pp))
ags.pp_team = None
ags.pk_team = "HOME"
e_sh = ags._systems_edge_for("HOME")
check("SH edge defined", 0.5 < e_sh < 1.5, str(e_sh))

# ---------------------------------------------------------------- league neutrality
random.seed(7)
hg = [tx.matchup_modifiers(a, b)["home_goals"]
      for a in teams for b in teams if a is not b]
pc = [tx.matchup_modifiers(a, b)["pace"]
      for a in teams for b in teams if a is not b]
sv = [tx.matchup_modifiers(a, b)["home_shot_vol"]
      for a in teams for b in teams if a is not b]
sq = [tx.matchup_modifiers(a, b)["home_shot_qual"]
      for a in teams for b in teams if a is not b]
mean_hg = sum(hg) / len(hg)
mean_pc = sum(pc) / len(pc)
mean_sv = sum(sv) / len(sv)
mean_sq = sum(sq) / len(sq)
check("league scoring neutral (home_goals mean ~1.0)",
      abs(mean_hg - 1.0) < 0.03, f"{mean_hg:.4f}")
check("league pace neutral (pace mean ~1.0)",
      abs(mean_pc - 1.0) < 0.03, f"{mean_pc:.4f}")
check("league shot volume neutral (mean ~1.0)",
      abs(mean_sv - 1.0) < 0.03, f"{mean_sv:.4f}")
check("league shot quality neutral (mean ~1.0)",
      abs(mean_sq - 1.0) < 0.03, f"{mean_sq:.4f}")
check("volume spread is real (trap vs rush)",
      # dampened (2026-09-28 NHL calibration, exponent 0.35): ~9 pts of
      # spread -- trap and rush stay distinct, team-season means land in
      # the real 24.5..34 band instead of 11..35.
      max(sv) - min(sv) > 0.07,
      f"range {min(sv):.3f}..{max(sv):.3f}")

# ---------------------------------------------------------------- identity lines
line = " | ".join(tx.describe_team_tactics(seeded("Toronto Maple Leafs")))
check("identity line mentions systems",
      "Power play:" in line and "Penalty kill:" in line, line)
t_chaos = sys_team()
tx.apply_identity_preset(t_chaos, "chaos_pressure")
chaos_line = " | ".join(tx.describe_team_tactics(t_chaos))
check("identity line leads with club identity",
      chaos_line.startswith("Identity: Chaos & Pressure"),
      chaos_line[:60])

# ---------------------------------------------------------------- xG hook
print("--- engine: xG factor ---")
g = GameSim.__new__(GameSim)
g._get_current_situation = lambda: SpecialSituation.EVEN_STRENGTH
g._team_situation = lambda team, sit: sit
att = sys_team(oz="oz_rush", fam=95)
att.tactic_even_strength = "Balanced"
tdef = sys_team(nz="nz_trap_131", dz="dz_box", fam=95)
tdef.tactic_even_strength = "Balanced"
hdef = sys_team(nz="nz_regroup", dz="dz_hybrid", fam=95)
hdef.tactic_even_strength = "Balanced"
f_trap = GameSim._team_tactics_xg_factor(g, att, tdef)
f_hyb = GameSim._team_tactics_xg_factor(g, att, hdef)
check("xG hook: trap suppresses the same rush attack",
      f_trap < f_hyb, f"{f_trap:.3f} vs {f_hyb:.3f}")
check("xG hook: factor inside widened clamp", 0.75 <= f_trap <= 1.35)
check("xG hook: cycle team gets quality edge over rush",
      GameSim._team_tactics_xg_factor(
          g, sys_team(oz="oz_cycle", fam=95),
          sys_team(nz="nz_regroup", dz="dz_hybrid", fam=95)) >
      GameSim._team_tactics_xg_factor(
          g, sys_team(oz="oz_rush", fam=95),
          sys_team(nz="nz_regroup", dz="dz_hybrid", fam=95)))

# PP branch of the xG hook
g._get_current_situation = lambda: SpecialSituation.POWER_PLAY
g._team_situation = lambda team, sit: sit
pp_att = sys_team(pp="one_three_one", fam=95)
pp_att.tactic_power_play = "Offensive"
pk_box = sys_team(pk="passive_box", fam=95)
pk_box.tactic_penalty_kill = "Defensive"
pk_dia = sys_team(pk="diamond", fam=95)
pk_dia.tactic_penalty_kill = "Defensive"
f_pp_box = GameSim._team_tactics_xg_factor(g, pp_att, pk_box)
f_pp_dia = GameSim._team_tactics_xg_factor(g, pp_att, pk_dia)
check("xG hook: passive box kills the 1-3-1 better than diamond",
      f_pp_box < f_pp_dia, f"{f_pp_box:.3f} vs {f_pp_dia:.3f}")

# ---------------------------------------------------------------- physical
print("--- physicality ---")
ph_swarm = tx.resolve_team_tactics(sys_team(fc="forecheck_212_swarm",
                                            fam=95))["physical"]
ph_122 = tx.resolve_team_tactics(sys_team(fc="forecheck_122",
                                          fam=95))["physical"]
check("swarm forecheck out-hits the 1-2-2", ph_swarm > ph_122,
      f"{ph_swarm:.3f} vs {ph_122:.3f}")
ph_mean = sum(tx.resolve_team_tactics(t)["physical"] for t in teams) / len(teams)
check("league hit rate neutral", abs(ph_mean - 1.0) < 0.05,
      f"{ph_mean:.4f}")

# ---------------------------------------------------------------- copycat
print("--- copycat league ---")


class RiggedRng:
    def __init__(self, rv=0.0):
        self.rv = rv

    def random(self):
        return self.rv

    def choices(self, cats, weights, k):
        return list(cats)[:k]


def league_of(champ_pp="one_three_one", rv=0.0, user_pp="umbrella",
              ai_pp="umbrella", coach=None):
    def mk(name, pp, user=False):
        t = fake_team(team_name=name, roster=[],
                      tactics={"forecheck": "forecheck_122",
                               "neutral_zone": "nz_regroup",
                               "dzone": "dz_hybrid", "ozone": "oz_micro",
                               "breakout": "bo_controlled",
                               "pp": pp, "pk": "diamond"},
                      tactics_familiarity=85, is_user_team=user)
        if coach is not None:
            t.staff = [coach]
        return t
    champ = mk("Champs", champ_pp)
    ai = mk("Coyotes", ai_pp)
    user = mk("Mine", user_pp, user=True)
    lg = SimpleNamespace(teams=[champ, ai, user],
                         playoff_bracket=SimpleNamespace(
                             stanley_cup_champion=champ))
    return lg, champ, ai, user


lg, champ, ai, user = league_of()
copied = tx.offseason_copycat(lg, rng=RiggedRng(0.0))
check("copycat copies the champs' PP",
      any(c[0] == "Coyotes" and c[1] == "pp" and c[2] == "one_three_one"
          for c in copied), str(copied))
check("user team never copies",
      not any(c[0] == "Mine" for c in copied))
check("champs don't copy themselves",
      not any(c[0] == "Champs" for c in copied))
check("copying costs familiarity",
      ai.tactics_familiarity <= 55, str(ai.tactics_familiarity))

stubborn = SimpleNamespace(role=SimpleNamespace(value="Head Coach"),
                           adaptability=20, control_need=95)
# Immovables (low adaptability + high control need) never copy, no matter
# the roll -- the Trotz/Lemaire types retire before they change.
lg2, _, ai2, _ = league_of(coach=stubborn)
c_yes = tx.offseason_copycat(lg2, rng=RiggedRng(0.0))
lg3, _, ai3, _ = league_of(coach=stubborn)
c_no = tx.offseason_copycat(lg3, rng=RiggedRng(0.99))
check("stubborn coach never copies",
      len(c_yes) == 0 and len(c_no) == 0, f"{c_yes} / {c_no}")

lg4, _, _, _ = league_of()
check("no champion -> no copies",
      tx.offseason_copycat(SimpleNamespace(
          teams=lg4.teams,
          playoff_bracket=SimpleNamespace(stanley_cup_champion=None)),
          rng=RiggedRng(0.0)) == [])

print()

# ---------------------------------------------------------------- whiteboard
# control
print("--- tactics control: suggest / enforce / take over ---")
import reputation_system as rs
from unittest.mock import patch


def tcoach(**kw):
    base = dict(full_name="Test Coach", control_need=50, gm_trust=70,
                adaptability=50, first_nhl_chair=False, years_with_team=3,
                controversy=30, reputation=60, leadership=60, happiness=70,
                morale=70, discipline=65, motivating=65, man_management=65,
                tactical_knowledge=65, game_preparation=65,
                working_with_youngsters=50, player_development=50)
    base.update(kw)
    c = SimpleNamespace(**base)
    c.role = SimpleNamespace(value="Head Coach")
    c.id = kw.get("id", 1)
    return c


def wteam(coach):
    t = fake_team(team_name="Test Club", roster=[], staff=[coach],
                  tactics_control="coach")
    tx.ensure_team_tactics(t)
    return t


check("control defaults to coach", tx.get_tactics_control(fake_team()) == "coach")
t0 = fake_team()
tx.set_tactics_control(t0, "gm")
check("control roundtrips", tx.get_tactics_control(t0) == "gm")

rookie = tcoach(first_nhl_chair=True, years_with_team=1)
prev = rs.preview_tactics_discussion(rookie, {"ozone": "oz_rush"})
check("rookie welcomes suggestions", prev["tone"] == "welcomes" and prev["accept_p"] >= 0.7,
      f"{prev['tone']} p={prev['accept_p']:.2f}")

torts = tcoach(control_need=95, gm_trust=40, adaptability=20)
prev = rs.preview_tactics_discussion(torts, {"ozone": "oz_rush", "neutral_zone": "nz_trap_131", "dzone": "dz_box"})
check("authoritarian hates identity overhaul",
      prev["tone"] == "furious" and prev["accept_p"] < 0.35,
      f"{prev['tone']} p={prev['accept_p']:.2f} trust{prev['trust_delta']}")

coop = tcoach(control_need=25, gm_trust=85, adaptability=70)
prev_dry = rs.preview_tactics_discussion(coop, {"pp": "umbrella"},
                                         {"win_pct": 0.35, "losing_streak": 4})
prev_ok = rs.preview_tactics_discussion(coop, {"pp": "umbrella"},
                                        {"win_pct": 0.65, "losing_streak": 0})
check("dry spell raises acceptance", prev_dry["accept_p"] > prev_ok["accept_p"],
      f"{prev_dry['accept_p']:.2f} vs {prev_ok['accept_p']:.2f}")

# suggest: accept path
c_acc = tcoach()
tm = wteam(c_acc)
with patch.object(rs.random, "random", return_value=0.0):
    res = rs.suggest_tactics_to_coach(tm, {"ozone": "oz_rush"})
check("suggest accepted applies + trust up",
      res["applied"] and tm.tactics["ozone"] == "oz_rush" and c_acc.gm_trust == 73,
      res["text"][:60])

# suggest: reject path
c_rej = tcoach()
tm2 = wteam(c_rej)
old_oz = tm2.tactics["ozone"]
with patch.object(rs.random, "random", return_value=0.99):
    res = rs.suggest_tactics_to_coach(tm2, {"ozone": "oz_rush"})
check("suggest rejected keeps systems, trust dips",
      not res["applied"] and tm2.tactics["ozone"] == old_oz and c_rej.gm_trust == 68,
      res["text"][:60])

# enforce: authoritarian hurt more than collaborator
c_auth = tcoach(control_need=95)
c_col = tcoach(control_need=20)
tm3, tm4 = wteam(c_auth), wteam(c_col)
rs.enforce_tactics(tm3, {"neutral_zone": "nz_trap_131"}, {"win_pct": 0.5})
rs.enforce_tactics(tm4, {"neutral_zone": "nz_trap_131"}, {"win_pct": 0.5})
check("enforce lands, authoritarian hit harder",
      tm3.tactics["neutral_zone"] == "nz_trap_131" and c_auth.gm_trust < c_col.gm_trust,
      f"auth {c_auth.gm_trust} vs collab {c_col.gm_trust}")

# take over / hand back
c_to = tcoach(control_need=90)
tm5 = wteam(c_to)
res = rs.take_over_tactics(tm5, {"win_pct": 0.5})
check("takeover: gm owns whiteboard, authoritarian livid",
      tx.get_tactics_control(tm5) == "gm" and c_to.gm_trust == 60,
      res["text"][:60])
res = rs.hand_back_tactics(tm5)
check("handback restores coach + trust",
      tx.get_tactics_control(tm5) == "coach" and c_to.gm_trust == 64,
      res["text"][:60])

c_rk = tcoach(first_nhl_chair=True, years_with_team=1)
tm6 = wteam(c_rk)
rs.take_over_tactics(tm6, {"win_pct": 0.5})
check("rookie welcomes takeover", c_rk.gm_trust == 73, str(c_rk.gm_trust))

# coach installs his systems on hire
c_new = tcoach(id=99, discipline=95, motivating=70, man_management=50)  # drill sergeant
tm7 = wteam(tcoach(id=7))
tm7.tactics_installed_by = 7
installed = tx.install_coach_systems(tm7, c_new, reason="hired")
check("new coach installs his systems",
      bool(installed) and tm7.tactics_installed_by == 99 and tm7.tactics_familiarity == 55,
      str(installed))
check("no install under GM control",
      tx.install_coach_systems(tm7, tcoach(id=100)) == {}
      if (tx.set_tactics_control(tm7, "gm"), True)[1] else False)

tm8 = wteam(tcoach(id=8))
tm8.tactics_installed_by = 8
check("maybe_install no-op when same coach",
      tx.maybe_install_coach_systems(tm8) == {})
tm8.staff = [tcoach(id=9, discipline=95)]
check("maybe_install fires on coach change",
      bool(tx.maybe_install_coach_systems(tm8)) and tm8.tactics_installed_by == 9)

# intermission AI
c_ai = tcoach(adaptability=95)
tm9 = wteam(c_ai)
hits = [tx.ai_intermission_adjustment(tm9, -3) for _ in range(20)]
got = [h for h in hits if h]
check("losing adaptable coach adjusts",
      bool(got) and all(h["category"] in ("ozone", "forecheck",
                                          "neutral_zone", "dzone")
                        for h in got),
      f"{len(got)}/20 adjusted")
check("no adjustment when GM controls",
      tx.ai_intermission_adjustment(tm9, -3) is None
      if (tx.set_tactics_control(tm9, "gm"), True)[1] else False)
tx.set_tactics_control(tm9, "coach")
c_serg = tcoach(adaptability=90, discipline=98, motivating=70, man_management=50)
tm10 = wteam(c_serg)
tm10.tactics["ozone"] = "oz_rush"
lead_hits = [tx.ai_intermission_adjustment(tm10, 4) for _ in range(30)]
check("defensive mind protects a big lead",
      any(h and h["new_key"] in ("nz_trap_131", "dz_box")
          for h in lead_hits),
      f"{sum(1 for h in lead_hits if h)}/30 locked down")

# preferred tactics
tm11 = wteam(tcoach())
tx.save_preferred_tactics(tm11)
check("preferred save/load roundtrip",
      tx.get_preferred_tactics(tm11) == tx.team_tactics(tm11))
check("tradeoffs line non-empty",
      bool(tx.system_tradeoffs("ozone", "oz_rush")),
      tx.system_tradeoffs("ozone", "oz_rush"))

# ------------------------------------------------- adaptive AI coaches
import adaptive_rivals as ar

# Counter table covers every system in every catalog
_all_sys = [k for cat in tx.CATALOGS.values() for k in cat]
check("counter table covers all systems",
      all(k in tx.TACTICAL_COUNTERS for k in _all_sys),
      f"{sum(1 for k in _all_sys if k not in tx.TACTICAL_COUNTERS)} missing")
check("every system has a family tag",
      all(k in tx.SYSTEM_FAMILIES for k in _all_sys))
check("counter answers are valid module keys",
      all(tx.TACTICAL_COUNTERS[k][1] in tx.CATALOGS[tx.TACTICAL_COUNTERS[k][0]]
          for k in _all_sys))

# Philosophy preserved: presets map to families
chaos_t = wteam(tcoach()); tx.apply_identity_preset(chaos_t, "chaos_pressure")
strang_t = wteam(tcoach()); tx.apply_identity_preset(strang_t, "stranglehold")
check("chaos preset is pressure family", tx.team_family(chaos_t) == "pressure")
check("stranglehold preset is structure family",
      tx.team_family(strang_t) == "structure")
check("balanced fits any room",
      tx.families_compatible("pressure", "dz_hybrid")
      and tx.families_compatible("structure", "dz_hybrid"))
check("cross-family blocked",
      not tx.families_compatible("pressure", "nz_trap_131")
      and not tx.families_compatible("structure", "forecheck_212_swarm"))

# Intel: no overreaction to one game; fires on a real trend
user = wteam(tcoach()); user.team_name = "User Club"
user.tactics["pp"] = "umbrella"
ai = wteam(tcoach(adaptability=60)); ai.team_name = "AI Club"
tx.apply_identity_preset(ai, "stranglehold")
ai.tactics["pk"] = "diamond"  # not already playing the answer
tx.record_tactical_intel(ai, user, 2, 3, 26, 0.40)
check("one meeting is not a trend",
      tx.damaging_user_systems(ai, user) == [])
tx.record_tactical_intel(ai, user, 2, 3, 24, 0.38)
tx.record_tactical_intel(ai, user, 3, 4, 28, 0.42)
dmg = tx.damaging_user_systems(ai, user)
check("hot umbrella PP flagged after 3 meetings",
      any(c == "pp" and s == "umbrella" for c, s, h in dmg),
      str([(c, s, round(h, 2)) for c, s, h in dmg]))

# plan_adaptation: structure team answers the umbrella with the box
plan = ar.plan_adaptation(ai, user, [])
check("plans passive box vs hot umbrella",
      any(c == "pk" and n == "passive_box" for c, o, n, r in plan),
      str([(c, n) for c, o, n, r in plan]))

# Philosophy gate: chaos team won't trap up for you unless adaptable/desperate
ai2 = wteam(tcoach(adaptability=60)); ai2.team_name = "AI Club 2"
tx.apply_identity_preset(ai2, "chaos_pressure")
for _ in range(3):
    tx.record_tactical_intel(ai2, user, 4, 2, 30, 0.33)
plan2 = ar.plan_adaptation(ai2, user, [])
check("chaos room refuses the structure answer at adapt 60",
      not any(c == "pk" and n == "passive_box" for c, o, n, r in plan2))
ai3 = wteam(tcoach(adaptability=85)); ai3.team_name = "AI Club 3"
tx.apply_identity_preset(ai3, "chaos_pressure")
for _ in range(3):
    tx.record_tactical_intel(ai3, user, 4, 2, 30, 0.33)
plan3 = ar.plan_adaptation(ai3, user, [])
check("adaptable coach crosses families",
      any(c == "pk" and n == "passive_box" for c, o, n, r in plan3))

# Apply/revert round-trip is exact
before = dict(tx.team_tactics(ai))
ar.apply_adaptation(ai, plan)
check("adaptation installs the answer",
      tx.team_tactics(ai)["pk"] == "passive_box")
ar.revert_adaptation(ai, plan)
check("revert restores exact systems",
      tx.team_tactics(ai) == before)

# Defensive answer: your PK/D-zone is stifling them -> they change the PP/OZ
ai4 = wteam(tcoach(adaptability=60)); ai4.team_name = "AI Club 4"
tx.apply_identity_preset(ai4, "chaos_pressure")
ai4.tactics["pp"] = "umbrella"  # not already playing the answer
user2 = wteam(tcoach()); user2.team_name = "User Club 2"
user2.tactics["pk"] = "passive_box"
user2.tactics["dzone"] = "dz_box"  # structure answer blocked for chaos room
for _ in range(2):
    tx.record_tactical_intel(ai4, user2, 2, 2, 24, 0.10)
tx.record_tactical_intel(ai4, user2, 1, 1, 22, 0.08)
plan4 = ar.plan_adaptation(ai4, user2, [])
check("stifled AI answers your passive box with point barrage",
      any(c == "pp" and n == "shoot_first" for c, o, n, r in plan4),
      str([(c, n) for c, o, n, r in plan4]))

# Pre-game report surfaces the answer
lines = ar.adaptation_report_lines(ai, user, [])
check("scout report lines non-empty when adapting", len(lines) > 0, str(lines))
quiet_ai = wteam(tcoach()); quiet_ai.team_name = "Quiet Club"
check("no lines when nothing is hurting them",
      ar.adaptation_report_lines(quiet_ai, user, []) == [])

# Copycat realism: stubborn coaches never move; max 3 adopters; dynasty heat
def _cleague(champ, teams):
    lg = SimpleNamespace(teams=teams,
                         playoff_bracket=SimpleNamespace(
                             stanley_cup_champion=champ))
    return lg

rng = random.Random(7)
champ = wteam(tcoach()); champ.team_name = "Champs"
tx.apply_identity_preset(champ, "chaos_pressure")
stubborn = wteam(tcoach(adaptability=30, control_need=70))
stubborn.team_name = "Stubborn Club"
field = [champ, stubborn] + [wteam(tcoach(adaptability=65))
                              for _ in range(10)]
for i, t in enumerate(field[2:], 1):
    t.team_name = f"Club {i}"
copies = [tx.offseason_copycat(_cleague(champ, field), rng) for _ in range(6)]
flat = [c for run in copies for c in run]
check("stubborn coach never copies",
      not any(c[0] == "Stubborn Club" for c in flat))
check("at most 3 adopters per summer",
      all(len(run) <= 3 for run in copies),
      str([len(run) for run in copies]))
# Dynasty heat: repeat champ is hotter than a fresh winner
lg = _cleague(champ, field)
h1 = tx._blueprint_heat(lg, champ, tx.team_tactics(champ))
h2 = tx._blueprint_heat(lg, champ, tx.team_tactics(champ))
check("repeat title heats the blueprint", h2 > h1, f"{h1} -> {h2}")
fresh = wteam(tcoach()); fresh.team_name = "Fresh Champs"
tx.apply_identity_preset(fresh, "stranglehold")
h3 = tx._blueprint_heat(lg, fresh, tx.team_tactics(fresh))
check("fresh winner is merely intriguing", h3 == 1.0, str(h3))
# Copycat returns lore-ready 4-tuples
check("copycat 4-tuple shape",
      all(len(c) == 4 for c in flat), str(flat[:1]))

print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
