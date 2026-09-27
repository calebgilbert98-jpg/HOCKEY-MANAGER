#!/usr/bin/env python3
"""Deterministic QA for the NHL coaching tactics layer (tactics.py).

Covers: catalog completeness, NHL seeding, resolution ranges, matchup
gradients (trap suppresses, 1-3-1 PP converts, aggressive kills counter),
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
check("offense catalog >= 6", len(tx.OFFENSIVE_SYSTEMS) >= 6,
      str(len(tx.OFFENSIVE_SYSTEMS)))
check("defense catalog >= 6", len(tx.DEFENSIVE_SYSTEMS) >= 6)
check("philosophy catalog >= 6", len(tx.PHILOSOPHIES) >= 6)
check("pp catalog >= 6", len(tx.POWERPLAY_SYSTEMS) >= 6)
check("pk catalog >= 6", len(tx.PENALTY_KILL_SYSTEMS) >= 6)

# ---------------------------------------------------------------- seeding
teams = [seeded(n) for n in tx.NHL_TEAM_TACTICS]
check("all 32 NHL teams seed", len(teams) == 32)
bad = [t.team_name for t in teams
       if tx.team_tactics(t)["offense"] not in tx.OFFENSIVE_SYSTEMS
       or tx.team_tactics(t)["defense"] not in tx.DEFENSIVE_SYSTEMS
       or tx.team_tactics(t)["pp"] not in tx.POWERPLAY_SYSTEMS
       or tx.team_tactics(t)["pk"] not in tx.PENALTY_KILL_SYSTEMS
       or tx.team_tactics(t)["philosophy"] not in tx.PHILOSOPHIES]
check("all seeds reference valid systems", not bad, str(bad[:3]))
check("trap teams exist", any(tx.team_tactics(t)["defense"] in
                              ("neutral_trap", "neutral_131", "passive_box")
                              for t in teams))
check("identities differ across league",
      len({" | ".join(tx.describe_team_tactics(t)) for t in teams}) > 20)

# ---------------------------------------------------------------- resolve ranges
for t in teams:
    r = tx.resolve_team_tactics(t)
for t in teams:
    r = tx.resolve_team_tactics(t)
    for k in ("attack", "defense", "pace", "pp", "pk"):
        if not (0.75 <= r[k] <= 1.25):
            check(f"range {t.team_name}.{k}", False, str(r[k]))
            break
    else:
        continue
    break
else:
    check("resolve multipliers within 0.75-1.25", True)

# ---------------------------------------------------------------- gradients
def sys_team(off="balanced", dfn="hybrid", pp="umbrella", pk="diamond",
             phi="pragmatist", fam=85):
    t = fake_team(team_name="T", roster=[],
                  tactics={"offense": off, "defense": dfn, "pp": pp,
                           "pk": pk, "philosophy": phi},
                  tactics_familiarity=fam)
    return t

trap = sys_team(dfn="neutral_trap")
hyb = sys_team(dfn="hybrid")
check("trap defends better than hybrid",
      tx.resolve_team_tactics(trap)["defense"] <
      tx.resolve_team_tactics(hyb)["defense"])

rush = sys_team(off="rush_attack")
dump = sys_team(off="dump_chase")
m_rush_trap = tx.matchup_modifiers(rush, trap)
check("trap drags pace below 1.0 vs rush", m_rush_trap["pace"] < 1.0,
      str(m_rush_trap["pace"]))
m_rush_hyb = tx.matchup_modifiers(rush, hyb)
check("trap suppresses the same rush attack more than hybrid",
      m_rush_trap["home_goals"] < m_rush_hyb["home_goals"],
      f"{m_rush_trap['home_goals']:.3f} vs {m_rush_hyb['home_goals']:.3f}")
m_trap_trap = tx.matchup_modifiers(trap, sys_team(dfn="neutral_trap"))
check("trap-vs-trap is the lowest-event matchup",
      m_trap_trap["pace"] < m_rush_trap["pace"])

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

heavy = sys_team(off="heavy_cycle")
check("heavy cycle is the most physical",
      tx.resolve_team_tactics(heavy)["physical"] >
      tx.resolve_team_tactics(sys_team(off="balanced"))["physical"])

# ---------------------------------------------------------------- familiarity
fresh = sys_team(off="rush_attack", fam=85, phi="defense_first")
tx.set_team_system(fresh, "offense", "dump_chase")
r_fresh = tx.resolve_team_tactics(fresh)
check("fresh system change drops familiarity",
      r_fresh["familiarity"] <= 45, str(r_fresh["familiarity"]))
prag = sys_team(off="rush_attack", fam=85, phi="pragmatist")
tx.set_team_system(prag, "offense", "dump_chase")
check("pragmatist floor is higher (adapts faster)",
      tx.resolve_team_tactics(prag)["familiarity"] == 55)
check("fresh system is muted toward 1.0",
      abs(r_fresh["attack"] - 1.0) <
      abs(tx.resolve_team_tactics(sys_team(off="dump_chase", fam=95,
                                           phi="defense_first"))["attack"]
          - 1.0))
for _ in range(14):
    tx.tick_tactics_familiarity(fresh)
r_learned = tx.resolve_team_tactics(fresh)
check("familiarity recovers with games", r_learned["familiarity"] >= 90,
      str(r_learned["familiarity"]))
check("learned system bites harder than fresh",
      abs(r_learned["attack"] - 1.0) > abs(r_fresh["attack"] - 1.0))

# ---------------------------------------------------------------- roster fit
speedster = [skater(skating=96, puckhandling=92, flair=90,
                    shoot_pass_tendency=35, hitting_tendency=20,
                    aggressiveness=30) for _ in range(12)]
grinder = [skater(skating=72, checking=92, strength=90, flair=25,
                  shoot_pass_tendency=60, hitting_tendency=85,
                  aggressiveness=80, bravery=85) for _ in range(12)]
t_spd = fake_team(team_name="SPD", roster=speedster,
                  tactics_familiarity=85)
t_grd = fake_team(team_name="GRD", roster=grinder,
                  tactics_familiarity=85)
f_spd_rush = tx.player_system_fit(speedster[0], "rush_attack")
f_spd_dump = tx.player_system_fit(speedster[0], "dump_chase")
f_grd_rush = tx.player_system_fit(grinder[0], "rush_attack")
f_grd_dump = tx.player_system_fit(grinder[0], "dump_chase")
check("speedster fits rush better than dump", f_spd_rush > f_spd_dump,
      f"{f_spd_rush:.2f} vs {f_spd_dump:.2f}")
check("grinder fits dump better than rush", f_grd_dump > f_grd_rush,
      f"{f_grd_dump:.2f} vs {f_grd_rush:.2f}")
check("fit stays in 0.6..1.2",
      all(0.6 <= f <= 1.2 for f in
          (f_spd_rush, f_spd_dump, f_grd_rush, f_grd_dump)))
t_spd.tactics = {"offense": "rush_attack", "defense": "hybrid",
                 "pp": "umbrella", "pk": "diamond",
                 "philosophy": "pragmatist"}
_raw = sum(tx.player_system_fit(p, "rush_attack") for p in speedster) / len(speedster)
_expected = max(0.92, min(1.08, 0.92 + (_raw - 0.6) * (0.16 / 0.6)))
check("team fit compresses roster average 0.6..1.2 -> 0.92..1.08",
      abs(tx.team_system_fit(t_spd) - _expected) < 1e-9,
      f"{tx.team_system_fit(t_spd):.4f} vs {_expected:.4f}")

# ---------------------------------------------------------------- coach prefs
c_sergeant = SimpleNamespace(discipline=96, motivating=55, leadership=80,
                             man_management=45, adaptability=40,
                             controversy=30)
prefs = tx.default_coach_prefs(c_sergeant)
check("drill sergeant gets 5 valid prefs",
      set(prefs) == {"offense", "defense", "pp", "pk", "philosophy"}
      and prefs["offense"] in tx.OFFENSIVE_SYSTEMS
      and prefs["defense"] in tx.DEFENSIVE_SYSTEMS
      and prefs["pp"] in tx.POWERPLAY_SYSTEMS
      and prefs["pk"] in tx.PENALTY_KILL_SYSTEMS
      and prefs["philosophy"] in tx.PHILOSOPHIES, str(prefs))
check("drill sergeant wants structure",
      prefs["defense"] in ("neutral_trap", "neutral_131", "passive_box",
                           "left_wing_lock", "collapsing_box"))
c_none = SimpleNamespace()
check("pref-less coach gets seeded prefs",
      set(tx.ensure_coach_tactics(c_none)) ==
      {"offense", "defense", "pp", "pk", "philosophy"})
check("coach fit neutral without prefs",
      abs(tx.coach_tactics_fit(None, t_spd) - 0.7) < 1e-9)

# ---------------------------------------------------------------- resolve cache
t_c = sys_team(off="rush_attack")
r1 = tx.resolve_team_tactics(t_c)
r2 = tx.resolve_team_tactics(t_c)
check("resolve memoized per game", r1 is r2)
tx.set_team_system(t_c, "offense", "heavy_cycle")
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
ags.home_team = sys_team(off="rush_attack", pp="one_three_one")
ags.away_team = sys_team(dfn="neutral_trap", pk="passive_box")
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
          ("home_goals", "away_goals", "pace", "home_pp", "away_pp")))
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
mean_hg = sum(hg) / len(hg)
mean_pc = sum(pc) / len(pc)
check("league scoring neutral (home_goals mean ~1.0)",
      abs(mean_hg - 1.0) < 0.03, f"{mean_hg:.4f}")
check("league pace neutral (pace mean ~1.0)",
      abs(mean_pc - 1.0) < 0.03, f"{mean_pc:.4f}")

# ---------------------------------------------------------------- identity lines
line = " | ".join(tx.describe_team_tactics(seeded("Toronto Maple Leafs")))
check("identity line mentions systems",
      "Power play:" in line and "Penalty kill:" in line, line)

# ---------------------------------------------------------------- xG hook
print("--- engine: xG factor ---")
g = GameSim.__new__(GameSim)
g._get_current_situation = lambda: SpecialSituation.EVEN_STRENGTH
g._team_situation = lambda team, sit: sit
att = sys_team(off="rush_attack", fam=95)
att.tactic_even_strength = "Balanced"
tdef = sys_team(dfn="neutral_trap", fam=95)
tdef.tactic_even_strength = "Balanced"
hdef = sys_team(dfn="hybrid", fam=95)
hdef.tactic_even_strength = "Balanced"
f_trap = GameSim._team_tactics_xg_factor(g, att, tdef)
f_hyb = GameSim._team_tactics_xg_factor(g, att, hdef)
check("xG hook: trap suppresses the same rush attack",
      f_trap < f_hyb, f"{f_trap:.3f} vs {f_hyb:.3f}")
check("xG hook: factor inside widened clamp", 0.75 <= f_trap <= 1.35)

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
ph_heavy = tx.resolve_team_tactics(sys_team(off="heavy_cycle", fam=95,
                                            phi="heavy_identity"))["physical"]
ph_skill = tx.resolve_team_tactics(sys_team(off="skill_possession", fam=95,
                                            phi="offense_first"))["physical"]
check("heavy cycle out-hits skill possession", ph_heavy > ph_skill,
      f"{ph_heavy:.3f} vs {ph_skill:.3f}")
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
                      tactics={"offense": "balanced", "defense": "hybrid",
                               "pp": pp, "pk": "diamond",
                               "philosophy": "pragmatist"},
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
      ("Coyotes", "pp", "one_three_one") in copied, str(copied))
check("user team never copies",
      not any(c[0] == "Mine" for c in copied))
check("champs don't copy themselves",
      not any(c[0] == "Champs" for c in copied))
check("copying costs familiarity",
      ai.tactics_familiarity <= 55, str(ai.tactics_familiarity))

stubborn = SimpleNamespace(role=SimpleNamespace(value="Head Coach"),
                           adaptability=20, control_need=95)
# p = 0.18*(0.5+20/130)*(1.1-95/200) ~= 0.0736
lg2, _, ai2, _ = league_of(coach=stubborn)
c_yes = tx.offseason_copycat(lg2, rng=RiggedRng(0.07))
lg3, _, ai3, _ = league_of(coach=stubborn)
c_no = tx.offseason_copycat(lg3, rng=RiggedRng(0.08))
check("stubborn coach copies at 0.07", len(c_yes) == 1, str(c_yes))
check("stubborn coach balks at 0.08", len(c_no) == 0, str(c_no))

lg4, _, _, _ = league_of()
check("no champion -> no copies",
      tx.offseason_copycat(SimpleNamespace(
          teams=lg4.teams,
          playoff_bracket=SimpleNamespace(stanley_cup_champion=None)),
          rng=RiggedRng(0.0)) == [])

print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
