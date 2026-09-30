#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Deterministic QA for the tactics factor expansion (2026-09-28).

Covers: the four new event factors (pressure / discipline / blocks /
rush) on every even-strength catalog entry, seeded-league neutrality
(product-mean 1.0 on all four), identity gradients (swarm pressures,
box blocks, trap stays out of the box, rush tilts to shots), the
legacy slider fold-in (tactic_even_strength / power_play /
penalty_kill now live inside resolve_team_tactics -- the sims read one
channel), matchup_modifiers exposure, and international strength being
inclusive of every implemented player factor (form, morale, goalie
weight, bonds) with a hard performance ceiling.

No randomness: all seeds fixed.
"""
import random
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, ".")

import tactics as tx
import international as il

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


ES_CATS = ("forecheck", "neutral_zone", "dzone", "ozone", "breakout")
FACTORS = ("pressure", "discipline", "blocks", "rush")

# ------------------------------------------------------- catalog completeness
for cat in ES_CATS:
    for name, sy in tx.CATALOGS[cat].items():
        for k in FACTORS:
            check(f"catalog {cat}/{name} has {k}", k in sy)
            check(f"catalog {cat}/{name} {k} sane",
                  0.5 <= sy[k] <= 1.6, str(sy.get(k)))

# ------------------------------------------------------- seeded neutrality
seeds = list(tx.NHL_TEAM_TACTICS.values())
for k in FACTORS:
    m = sum(tx.FORECHECK_SYSTEMS[s["forecheck"]][k]
            * tx.NEUTRAL_ZONE_SYSTEMS[s["neutral_zone"]][k]
            * tx.DZONE_SYSTEMS[s["dzone"]][k]
            * tx.OZONE_SYSTEMS[s["ozone"]][k]
            * tx.BREAKOUT_SYSTEMS[s["breakout"]][k]
            for s in seeds) / len(seeds)
    check(f"seed product-mean {k} ~= 1.0", abs(m - 1.0) < 0.01, f"{m:.4f}")

# ------------------------------------------------------- identity gradients
def id_team(ident, **kw):
    t = fake_team(team_name=f"t_{ident}", tactics_familiarity=100, **kw)
    tx.ensure_team_tactics(t)
    tx.apply_identity_preset(t, ident)
    return tx.resolve_team_tactics(t)

chaos = id_team("chaos_pressure")
strangle = id_team("stranglehold")
check("chaos pressures more than stranglehold",
      chaos["pressure"] > strangle["pressure"],
      f"{chaos['pressure']:.3f} vs {strangle['pressure']:.3f}")
check("stranglehold blocks more than chaos",
      strangle["blocks"] > chaos["blocks"],
      f"{strangle['blocks']:.3f} vs {chaos['blocks']:.3f}")
check("chaos rushes more than stranglehold",
      chaos["rush"] > strangle["rush"],
      f"{chaos['rush']:.3f} vs {strangle['rush']:.3f}")
check("stranglehold more disciplined than chaos",
      strangle["discipline"] > chaos["discipline"],
      f"{strangle['discipline']:.3f} vs {chaos['discipline']:.3f}")

# ------------------------------------------------------- legacy slider fold-in
def slider_team(es="Balanced", pp="Offensive", pk="Defensive"):
    t = fake_team(team_name=f"sl_{es}_{pp}_{pk}", tactics_familiarity=100,
                  tactic_even_strength=es, tactic_power_play=pp,
                  tactic_penalty_kill=pk)
    tx.ensure_team_tactics(t)
    # pin every module to the neutral default so only the slider moves
    for cat, key in (("forecheck", "forecheck_122"),
                     ("neutral_zone", "nz_regroup"),
                     ("dzone", "dz_hybrid"), ("ozone", "oz_micro"),
                     ("breakout", "bo_controlled"),
                     ("pp", "umbrella"), ("pk", "diamond")):
        tx.set_team_system(t, cat, key)
    return tx.resolve_team_tactics(t)

base = slider_team()
voff = slider_team(es="Very Offensive")
check("legacy ES Very Offensive -> attack x1.08",
      abs(voff["attack"] / base["attack"] - 1.08) < 0.02,
      f"{voff['attack'] / base['attack']:.3f}")
vdef = slider_team(es="Very Defensive")
check("legacy ES Very Defensive -> defense x0.92",
      abs(vdef["defense"] / base["defense"] - 0.92) < 0.02,
      f"{vdef['defense'] / base['defense']:.3f}")
check("legacy ES Very Offensive quickens pace",
      voff["pace"] > base["pace"] > vdef["pace"])
pp_vo = slider_team(pp="Very Offensive")
check("legacy PP Very Offensive -> pp x(1.10/1.05)",
      abs(pp_vo["pp"] / base["pp"] - 1.10 / 1.05) < 0.02,
      f"{pp_vo['pp'] / base['pp']:.3f}")
pk_vd = slider_team(pk="Very Defensive")
check("legacy PK Very Defensive -> pk x(1.10/1.05)",
      abs(pk_vd["pk"] / base["pk"] - 1.10 / 1.05) < 0.02,
      f"{pk_vd['pk'] / base['pk']:.3f}")
# defaults keep the seeded league neutral: PP x1.05 cancels PK x1.05
check("default sliders keep pp/pk net neutral",
      abs(base["pp"] * (2.0 - base["pk"]) - 1.0) < 0.05,
      f"{base['pp'] * (2.0 - base['pk']):.3f}")

# ------------------------------------------------------- matchup exposure
m = tx.matchup_modifiers(fake_team(team_name="A", tactics_familiarity=100),
                         fake_team(team_name="B", tactics_familiarity=100))
for k in ("home_pressure", "away_pressure", "home_discipline",
          "away_discipline", "home_blocks", "away_blocks",
          "home_rush", "away_rush"):
    check(f"matchup exposes {k}", k in m and m[k] > 0, str(m.get(k)))

# ------------------------------------------------- international inclusivity
class IP:
    def __init__(self, ov, form=0.0, morale=70, goalie=False, nat="Canada"):
        self._ov = ov
        self.mesh_form = form
        self.morale = morale
        self.nationality = nat
        self.primary_position = SimpleNamespace(
            name="GOALIE" if goalie else "CENTER")
        self.is_injured = False
        self.intl_bonds = {}

    def overall_rating(self):
        return self._ov

    def full_name(self):
        return f"IP{self._ov}"


def nat_roster(mods=None):
    mods = mods or {}
    sk = [IP(**{**{"ov": 80}, **mods.get(i, {})}) for i in range(14)]
    gk = [IP(**{**{"ov": 80, "goalie": True}, **mods.get(f"g{i}", {})})
          for i in range(1)]
    clubs = [SimpleNamespace(team_name=f"Club{c}") for c in range(3)]
    pool = [(p, clubs[i % 3]) for i, p in enumerate(sk + gk)]
    return pool


r_base = il._build_roster(nat_roster(), "Canada")
r_hot = il._build_roster(
    nat_roster({i: {"form": 1.0} for i in range(14)}), "Canada")
check("hot form raises international strength",
      r_hot["strength"] > r_base["strength"],
      f"{r_hot['strength']:.2f} vs {r_base['strength']:.2f}")
r_cold = il._build_roster(
    nat_roster({i: {"form": -1.0} for i in range(14)}), "Canada")
check("cold form lowers international strength",
      r_cold["strength"] < r_base["strength"])
r_conf = il._build_roster(
    nat_roster({i: {"morale": 99} for i in range(14)}), "Canada")
check("high morale raises international strength",
      r_conf["strength"] > r_base["strength"])
# goalie weight: an elite goalie moves strength more than an elite skater
r_gk = il._build_roster(nat_roster({"g0": {"ov": 95}}), "Canada")
r_sk = il._build_roster(nat_roster({0: {"ov": 95}}), "Canada")
check("elite goalie outweighs elite skater",
      (r_gk["strength"] - r_base["strength"])
      > (r_sk["strength"] - r_base["strength"]),
      f"gk+{r_gk['strength'] - r_base['strength']:.2f} "
      f"vs sk+{r_sk['strength'] - r_base['strength']:.2f}")
# bonds: club pairs add chemistry
pool = nat_roster()
p0, t0 = pool[0]
p1, _ = pool[1]
p0.intl_bonds[p1.full_name()] = {"s": 4, "e": "Olympics 2026"}
r_bond = il._build_roster(pool, "Canada")
check("prior-tournament bonds raise strength",
      r_bond["strength"] > r_base["strength"],
      f"{r_bond['strength']:.2f} vs {r_base['strength']:.2f}")

# ------------------------------------------------- international performance
random.seed(11)
teams = []
for i in range(32):
    ros = [IP(random.uniform(68, 92),
              nat=random.choice(il.CANDIDATE_NATIONS)) for _ in range(23)]
    ros += [IP(random.uniform(68, 92), goalie=True,
               nat=random.choice(il.CANDIDATE_NATIONS)) for _ in range(3)]
    teams.append(SimpleNamespace(
        team_name=f"T{i}", league_name="National Hockey League",
        roster=ros, prospects=[]))
lg = SimpleNamespace(teams=teams, intl_held={}, intl_history=[],
                     playoff_bracket=None)
app = SimpleNamespace(league=lg)
t0 = time.perf_counter()
il.hold_olympics(app, 2026)
dt = time.perf_counter() - t0
check("full 32-team olympics resolves < 2s", dt < 2.0, f"{dt:.3f}s")
check("olympics resolves in milliseconds", dt < 0.5, f"{dt:.3f}s")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
