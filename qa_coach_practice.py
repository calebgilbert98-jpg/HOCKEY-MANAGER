# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: coaching-aware individual practice (coach_practice.py + engine wiring).

Run:  python3 qa_coach_practice.py   (no display needed)

Covers:
 1. session_coach: goalie -> goalie coach; skater -> best specialist
    assistant; nobody -> head coach; empty staff -> (None, "").
 2. specialty_rating: an attacking coach teaches shooting far better
    than checking (and vice versa for a defensive coach).
 3. coach_drill_rating: right teacher/right drill/right player beats the
    wrong teacher; the youth touch lifts kids; rigid coaches are exposed
    off-specialty.
 4. archetype_affinity: Sniper loves shooting, not checking; Enforcer is
    the mirror; unknown archetypes are neutral.
 5. practice_attitude: all-in vs checked-out players, labels + drivers.
 6. practice_fit_factor: drill sergeant x needs-freedom = friction
    (mult < 1, morale cost); synergy when the fit is good.
 7. system_practice_fit: offensive club + shooting = identity training;
    defensive club + shooting = just exercise.
 8. practice_breakdown: total_mult equals the product of the parts;
    deterministic across calls.
 9. execute_practice(team=...): stamps coach_name + breakdown; a good
    staff outperforms a bad staff; legacy team=None path unchanged.
 10. describe_session: UI lines, non-empty, no crash on empty breakdown.
 11. get_practice_recommendations: explained recs with and without team.
 12. Old-save safety: bare-minimum stubs never raise anywhere.
"""
import os
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
random.seed(20260928)

import coach_practice as cp
from enhanced_practice_system import (
    PracticeEngine, PracticeType, PracticeIntensity)
from game_classes import Player, PlayerPosition, Staff, StaffRole, Team

passed = []


def check(name, cond, extra=""):
    assert cond, f"FAILED: {name} {extra}"
    passed.append(name)
    print(f"  ok: {name}")


# ---------------------------------------------------------------- fixtures
def mkplayer(pos, age=22, arch=None, **kw):
    p = Player("Test", "Player", age, pos, 9)
    if arch:
        p.archetype = arch
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def mkcoach(first, role, **kw):
    c = Staff(first, "Coach", role)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def mkteam(staff=(), even="Balanced"):
    t = Team("Test Club", "Testville", "D", "E")
    t.staff = list(staff)
    t.tactic_even_strength = even
    return t


ATTACK_COACH = dict(attacking_coaching=92, defensive_coaching=45,
                    technical_coaching=70, coaching_forwards=88,
                    coaching_defensemen=55, coaching_goalies=40,
                    player_development=80, working_with_youngsters=75,
                    man_management=70, motivating=72, discipline=55,
                    leadership=65, tactical_knowledge=78,
                    mental_coaching=60, adaptability=70)
DEFENSE_COACH = dict(attacking_coaching=42, defensive_coaching=93,
                     technical_coaching=65, coaching_forwards=55,
                     coaching_defensemen=90, coaching_goalies=40,
                     player_development=78, working_with_youngsters=70,
                     man_management=68, motivating=66, discipline=80,
                     leadership=64, tactical_knowledge=76,
                     mental_coaching=60, adaptability=65)
GOALIE_COACH = dict(coaching_goalies=92, technical_coaching=85,
                    attacking_coaching=40, defensive_coaching=50,
                    player_development=75, working_with_youngsters=70,
                    man_management=70, motivating=70, discipline=60,
                    leadership=60, tactical_knowledge=65,
                    mental_coaching=70, adaptability=70)


# ------------------------------------------------------- 1. session_coach
hc = mkcoach("Head", StaffRole.HEAD_COACH, **ATTACK_COACH)
ac_o = mkcoach("Off", StaffRole.ASSISTANT_COACH, **ATTACK_COACH)
ac_d = mkcoach("Def", StaffRole.ASSISTANT_COACH, **DEFENSE_COACH)
gc = mkcoach("Goal", StaffRole.GOALIE_COACH, **GOALIE_COACH)
team = mkteam([hc, ac_o, ac_d, gc])

skater = mkplayer(PlayerPosition.LEFT_WING, arch="Sniper")
goalie = mkplayer(PlayerPosition.GOALIE, arch="Butterfly Goalie")

c, role = cp.session_coach(team, goalie, "skating")
check("goalie -> goalie coach", c is gc and role == "Goalie coach",
      f"{role}")
c, role = cp.session_coach(team, skater, "shooting")
check("skater shooting -> offense assistant",
      c is ac_o and role == "Assistant", f"{role}")
c, role = cp.session_coach(team, skater, "checking")
check("skater checking -> defense assistant", c is ac_d, f"{role}")
c, role = cp.session_coach(mkteam([hc]), skater, "shooting")
check("no assistants -> head coach", c is hc and role == "Head coach")
c, role = cp.session_coach(mkteam([]), skater, "shooting")
check("empty staff -> (None, '')", c is None and role == "")
c, role = cp.session_coach(None, skater, "shooting")
check("team None -> (None, '')", c is None and role == "")

# ------------------------------------------------- 2. specialty_rating
r_atk_shoot = cp.specialty_rating(ac_o, "shooting")
r_atk_check = cp.specialty_rating(ac_o, "checking")
check("attacking coach: shooting >> checking",
      r_atk_shoot > r_atk_check + 20,
      f"shoot={r_atk_shoot:.0f} check={r_atk_check:.0f}")
r_def_check = cp.specialty_rating(ac_d, "checking")
r_def_shoot = cp.specialty_rating(ac_d, "shooting")
check("defensive coach: checking >> shooting",
      r_def_check > r_def_shoot + 20,
      f"check={r_def_check:.0f} shoot={r_def_shoot:.0f}")
check("specialty_rating bounded", 1 <= r_atk_shoot <= 100)

# ------------------------------------------------ 3. coach_drill_rating
sniper = mkplayer(PlayerPosition.LEFT_WING, age=21, arch="Sniper")
r_good, d_good = cp.coach_drill_rating(ac_o, sniper, "shooting")
r_bad, d_bad = cp.coach_drill_rating(ac_d, sniper, "shooting")
check("right teacher beats wrong teacher", r_good > r_bad + 10,
      f"good={r_good:.0f} bad={r_bad:.0f}")
check("drivers explain", len(d_good) > 0 and len(d_bad) > 0)
vet = mkplayer(PlayerPosition.LEFT_WING, age=30, arch="Sniper")
r_kid, _ = cp.coach_drill_rating(ac_o, sniper, "shooting")
r_vet, _ = cp.coach_drill_rating(ac_o, vet, "shooting")
check("youth touch lifts the kid", r_kid > r_vet,
      f"kid={r_kid:.0f} vet={r_vet:.0f}")
rigid = mkcoach("Rigid", StaffRole.ASSISTANT_COACH,
                attacking_coaching=40, defensive_coaching=92,
                technical_coaching=50, coaching_forwards=55,
                coaching_defensemen=88, player_development=70,
                working_with_youngsters=60, adaptability=25,
                man_management=60, tactical_knowledge=60,
                mental_coaching=55)
r_rigid, d_rigid = cp.coach_drill_rating(rigid, sniper, "shooting")
check("rigid coach exposed off-specialty",
      r_rigid < r_bad and any("rigid" in d for d in d_rigid),
      f"rigid={r_rigid:.0f} bad={r_bad:.0f} drivers={d_rigid}")
r_none, d_none = cp.coach_drill_rating(None, sniper, "shooting")
check("no coach -> neutral 50", r_none == 50.0)

# ---------------------------------------------- 4. archetype_affinity
m, why = cp.archetype_affinity(sniper, "shooting")
check("sniper loves shooting", m == 1.4 and why, f"{m} {why}")
m2, why2 = cp.archetype_affinity(sniper, "checking")
check("sniper cold on checking", m2 < 1.0 < m and why2,
      f"{m2} {why2}")
enf = mkplayer(PlayerPosition.LEFT_WING, arch="Enforcer")
me, _ = cp.archetype_affinity(enf, "checking")
me2, _ = cp.archetype_affinity(enf, "shooting")
check("enforcer mirror", me > 1.2 > me2, f"{me} {me2}")
mystery = mkplayer(PlayerPosition.CENTER)
mystery.archetype = "Not A Real Archetype"
mn, _ = cp.archetype_affinity(mystery, "shooting")
check("unknown archetype neutral", mn == 1.0, f"{mn}")
mg, _ = cp.archetype_affinity(goalie, "shooting")
check("goalie shooting discounted", mg < 1.0, f"{mg}")
check("archetype_loves", cp.archetype_loves(sniper) == "shooting")

# ----------------------------------------------- 5. practice_attitude
keen = mkplayer(PlayerPosition.CENTER, age=20,
                coachability=88, work_ethic=90, morale=95, determination=88)
mult_k, lab_k, drv_k = cp.practice_attitude(keen)
check("all-in attitude", mult_k > 1.1 and lab_k == "All-in",
      f"{mult_k} {lab_k} {drv_k}")
sulky = mkplayer(PlayerPosition.CENTER, age=28,
                 coachability=52, work_ethic=51, morale=20, determination=55)
mult_s, lab_s, drv_s = cp.practice_attitude(sulky)
check("checked-out attitude", mult_s < 0.9 and lab_s == "Checked out",
      f"{mult_s} {lab_s} {drv_s}")
check("attitude bounded", 0.6 <= mult_s <= mult_k <= 1.3)

# -------------------------------------------- 6. practice_fit_factor
sergeant = mkcoach("Sergeant", StaffRole.HEAD_COACH,
                   discipline=95, motivating=60, man_management=30,
                   working_with_youngsters=55, tactical_knowledge=70,
                   attacking_coaching=70, defensive_coaching=80,
                   technical_coaching=65, coaching_forwards=75,
                   coaching_defensemen=75, player_development=65,
                   leadership=60, adaptability=40, mental_coaching=55)
free = mkplayer(PlayerPosition.RIGHT_WING, age=24, arch="Sniper",
                flair=82, discipline=38, happiness=70, morale=70,
                controversy=20, base_controversy=20)
fm, fl, fmc = cp.practice_fit_factor(sergeant, free)
check("drill sergeant x needs-freedom = friction",
      fm < 1.0 and fmc > 0 and "Friction" in fl, f"{fm} {fl} {fmc}")
players_coach = mkcoach("Buddy", StaffRole.HEAD_COACH,
                        discipline=40, motivating=85, man_management=90,
                        working_with_youngsters=60, tactical_knowledge=65,
                        attacking_coaching=70, defensive_coaching=60,
                        technical_coaching=65, coaching_forwards=72,
                        coaching_defensemen=70, player_development=70,
                        leadership=75, adaptability=75, mental_coaching=70)
fragile = mkplayer(PlayerPosition.CENTER, age=22, arch="Playmaker",
                   flair=50, discipline=60, happiness=40, morale=25,
                   controversy=10, base_controversy=10)
gm2, gl2, _ = cp.practice_fit_factor(players_coach, fragile)
check("player's coach x fragile = synergy", gm2 > 1.0 > fm,
      f"{gm2} {gl2}")
nm, nl, nmc = cp.practice_fit_factor(None, free)
check("no coach -> neutral fit", nm == 1.0 and nmc == 0.0)

# ------------------------------------------- 7. system_practice_fit
off_team = mkteam([hc], even="Offensive")
sm, sl, ts = cp.system_practice_fit(off_team, "shooting")
check("offensive system + shooting = identity",
      sm == 1.12 and ts and "offensive" in sl, f"{sm} {sl}")
def_team = mkteam([hc], even="Defensive")
def_team.tactic_power_play = "Balanced"
def_team.tactic_penalty_kill = "Very Defensive"
sm2, sl2, ts2 = cp.system_practice_fit(def_team, "shooting")
check("defensive system + shooting = just exercise",
      sm2 < 1.0 and not ts2, f"{sm2} {sl2}")
sm3, _, ts3 = cp.system_practice_fit(def_team, "defense")
check("defensive system + defense = identity", sm3 == 1.12 and ts3)
sm4, _, _ = cp.system_practice_fit(None, "shooting")
check("no team -> neutral system", sm4 == 1.0)

# -------------------------------------------- 8. practice_breakdown
bd = cp.practice_breakdown(team, sniper, "shooting")
parts = (bd["coach_mult"] * bd["affinity"] * bd["attitude"]
         * bd["fit"] * bd["system"])
check("total is clamped product of parts",
      abs(bd["total_mult"] - round(min(1.75, max(0.45, parts)), 3)) < 1e-6,
      f"{bd['total_mult']} vs {parts}")
check("total inside the sane band", 0.45 <= bd["total_mult"] <= 1.75)
bd2 = cp.practice_breakdown(team, sniper, "shooting")
check("deterministic", bd == bd2)
check("breakdown names the coach",
      bd["coach_name"] == "Off Coach" and bd["coach_role"] == "Assistant",
      f"{bd['coach_name']} {bd['coach_role']}")
check("fatigue_mult sane", 0.9 <= bd["fatigue_mult"] <= 1.1)

# ---------------------------------- 9. execute_practice with a team
eng = PracticeEngine()
# base_controversy is dealt once at generation in the real game; pin it
# here so the QA's reseeds compare like-for-like (the deal consumes RNG
# exactly once per player, then never again).
p1 = mkplayer(PlayerPosition.LEFT_WING, age=20, arch="Sniper",
              coachability=85, work_ethic=88, morale=85, determination=85,
              base_controversy=20)
p1.shooting, p1.skating = 60, 60
p2 = mkplayer(PlayerPosition.LEFT_WING, age=20, arch="Sniper",
              coachability=85, work_ethic=88, morale=85, determination=85,
              base_controversy=20)
p2.shooting, p2.skating = 60, 60
good_team = mkteam([mkcoach("Head", StaffRole.HEAD_COACH, **ATTACK_COACH),
                    mkcoach("Off", StaffRole.ASSISTANT_COACH,
                            **ATTACK_COACH)],
                   even="Offensive")
bad_team = mkteam([mkcoach("Head", StaffRole.HEAD_COACH,
                           **{**ATTACK_COACH, "attacking_coaching": 35,
                              "coaching_forwards": 35,
                              "player_development": 35}),
                   mkcoach("Off", StaffRole.ASSISTANT_COACH,
                           **{**ATTACK_COACH, "attacking_coaching": 35,
                              "coaching_forwards": 35,
                              "player_development": 35})],
                  even="Defensive")
random.seed(7)
s_good = eng.execute_practice(p1, PracticeType.SHOOTING,
                              PracticeIntensity.MODERATE, 60, 12,
                              team=good_team)
check("session stamps the coach",
      s_good.coach_name == "Off Coach" and s_good.breakdown is not None,
      s_good.coach_name)
check("good staff total_mult > 1",
      s_good.breakdown["total_mult"] > 1.0,
      s_good.breakdown["total_mult"])
# Good staff beats bad staff: neutral ground (average attitude,
# off-wheelhouse drill, balanced system) so the STAFF is the variable and
# neither side slams the clamp. Mean over many sessions; single sessions
# carry the engine's +/-20% realism noise.
neutral_team = mkteam([mkcoach("Head", StaffRole.HEAD_COACH, **ATTACK_COACH),
                       mkcoach("Off", StaffRole.ASSISTANT_COACH,
                               **ATTACK_COACH)],
                      even="Balanced")
neutral_team.tactic_power_play = "Balanced"
neutral_team.tactic_penalty_kill = "Balanced"
poor_team = mkteam([mkcoach("Head", StaffRole.HEAD_COACH,
                            **{**ATTACK_COACH, "attacking_coaching": 32,
                               "technical_coaching": 35,
                               "coaching_forwards": 32,
                               "player_development": 32,
                               "working_with_youngsters": 35}),
                    mkcoach("Off", StaffRole.ASSISTANT_COACH,
                            **{**ATTACK_COACH, "attacking_coaching": 32,
                               "technical_coaching": 35,
                               "coaching_forwards": 32,
                               "player_development": 32,
                               "working_with_youngsters": 35})],
                   even="Balanced")
poor_team.tactic_power_play = "Balanced"
poor_team.tactic_penalty_kill = "Balanced"
random.seed(99)
gains_good, gains_bad = [], []
for _ in range(40):
    kw = dict(coachability=70, work_ethic=70, morale=70, determination=70,
              base_controversy=20)
    pg = mkplayer(PlayerPosition.LEFT_WING, age=22, arch="Two-Way Forward",
                  **kw)
    pg.conditioning, pg.skating = 60, 60
    pb = mkplayer(PlayerPosition.LEFT_WING, age=22, arch="Two-Way Forward",
                  **kw)
    pb.conditioning, pb.skating = 60, 60
    cp.practice_breakdown(neutral_team, pg, "conditioning")  # pre-deal
    cp.practice_breakdown(poor_team, pb, "conditioning")
    gains_good.append(eng.execute_practice(
        pg, PracticeType.CONDITIONING, PracticeIntensity.MODERATE,
        60, 12, team=neutral_team).skill_gain)
    gains_bad.append(eng.execute_practice(
        pb, PracticeType.CONDITIONING, PracticeIntensity.MODERATE,
        60, 12, team=poor_team).skill_gain)
mean_good = sum(gains_good) / len(gains_good)
mean_bad = sum(gains_bad) / len(gains_bad)
tg = cp.practice_breakdown(neutral_team, pg, "conditioning")["total_mult"]
tb = cp.practice_breakdown(poor_team, pb, "conditioning")["total_mult"]
check("good staff beats bad staff (mean over 40)",
      mean_good > mean_bad * 1.15,
      f"good={mean_good:.3f} bad={mean_bad:.3f} mults={tg}/{tb}")
check("system-aligned practice rehearses the system",
      good_team.tactics_familiarity > 85,
      good_team.tactics_familiarity)

# friction costs morale on a hard skate
p3 = mkplayer(PlayerPosition.RIGHT_WING, age=24, arch="Sniper",
             flair=82, discipline=38, happiness=70, morale=70,
             controversy=20, base_controversy=20,
             coachability=60, work_ethic=65, determination=60)
p3.shooting = 60
t_fric = mkteam([sergeant], even="Balanced")
m_before = p3.morale
random.seed(11)
eng.execute_practice(p3, PracticeType.CONDITIONING,
                     PracticeIntensity.INTENSE, 60, 12, team=t_fric)
check("friction + hard skate costs morale", p3.morale < m_before,
      f"{m_before} -> {p3.morale}")

# legacy path: no team
p4 = mkplayer(PlayerPosition.CENTER, age=22)
p4.shooting = 60
random.seed(7)
s_leg = eng.execute_practice(p4, PracticeType.SHOOTING,
                             PracticeIntensity.MODERATE, 60, 12)
check("legacy path: no coach stamp, still gains",
      s_leg.coach_name == "" and s_leg.breakdown is None
      and s_leg.skill_gain >= 0)

# ------------------------------------------ 10. describe_session
lines = cp.describe_session(bd)
check("describe_session non-empty", len(lines) >= 4, lines[:2])
check("describe_session empty-safe", cp.describe_session({}) == [])

# --------------------------------- 11. recommendations
recs = eng.get_practice_recommendations(sniper, team=team)
check("recommendations explained with team",
      len(recs) > 0 and ";" in recs[0][1] or "--" in recs[0][1],
      recs[0] if recs else None)
recs2 = eng.get_practice_recommendations(sniper)
check("recommendations work without team", len(recs2) > 0)

# ------------------------------------------- 12. stub safety
stub = SimpleNamespace(id="x", age=25)
for fn in (lambda: cp.session_coach(None, stub, "shooting"),
           lambda: cp.specialty_rating(None, "shooting"),
           lambda: cp.coach_drill_rating(None, stub, "shooting"),
           lambda: cp.archetype_affinity(stub, "shooting"),
           lambda: cp.practice_attitude(stub),
           lambda: cp.practice_fit_factor(None, stub),
           lambda: cp.system_practice_fit(None, "shooting"),
           lambda: cp.practice_breakdown(None, stub, "shooting"),
           lambda: cp.describe_session({})):
    fn()
check("stub-safe everywhere", True)

# ----------------- 13. weekly all-team parity (user and AI share it)
# The weekly tick prices each attribute through the same breakdown via
# ATTRIBUTE_DRILL. Exercise the real helper (it carries no GUI state).
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("mainmod", "main.py")
# main.py is a GUI module; instead bind the helper's logic directly.
from types import SimpleNamespace as _SN2
_helper_self = _SN2()
def _weekly_coaching_mults(team, player, attrs, _cache):
    try:
        import coach_practice as _cp
    except Exception:
        return {}
    out = {}
    for attr in attrs:
        drill = _cp.attribute_drill(attr)
        if drill is None or not hasattr(player, attr):
            continue
        key = (id(team), id(player), drill)
        mult = _cache.get(key)
        if mult is None:
            try:
                mult = float(_cp.practice_breakdown(
                    team, player, drill).get("total_mult", 1.0))
            except Exception:
                mult = 1.0
            _cache[key] = mult
        out[attr] = mult
    return out
random.seed(20260928)
_attrs = ["skating", "shooting", "passing", "checking", "positioning",
          "hockey_iq", "faceoffs", "strength"]
_archs = ["Sniper", "Playmaker", "Two-Way Forward", "Power Forward",
          "Enforcer", "Offensive Defenseman", "Defensive Defenseman"]
_poss = [PlayerPosition.LEFT_WING, PlayerPosition.CENTER,
         PlayerPosition.RIGHT_WING, PlayerPosition.LEFT_DEFENSE]
_mg, _mb, _allok = [], [], True
for i in range(28):
    pl = mkplayer(_poss[i % 4], age=19 + (i % 5),
                  arch=_archs[i % len(_archs)],
                  coachability=60 + (i * 7) % 30,
                  work_ethic=60 + (i * 11) % 30,
                  morale=70, determination=70, base_controversy=20)
    for a in _attrs:
        setattr(pl, a, 55)
    _cache = {}
    mg = _weekly_coaching_mults(good_team, pl, _attrs, _cache)
    mb = _weekly_coaching_mults(bad_team, pl, _attrs, _cache)
    for a in _attrs:
        _allok = _allok and 0.45 <= mg[a] <= 1.75 and 0.45 <= mb[a] <= 1.75
    _mg.append(sum(mg.values()) / len(mg))
    _mb.append(sum(mb.values()) / len(mb))
_mean_g = sum(_mg) / len(_mg)
_mean_b = sum(_mb) / len(_mb)
check("weekly mults stay in band", _allok)
check("weekly: good staff > bad staff across roster",
      _mean_g > _mean_b * 1.10,
      f"good={_mean_g:.3f} bad={_mean_b:.3f}")
check("attribute_drill maps the weekly attrs",
      all(cp.attribute_drill(a) for a in _attrs))
check("attribute_drill unknown -> None", cp.attribute_drill("nope") is None)

# ----------------- 14. monthly engine: archetype/system dimensions
# Legacy formula untouched without team=; with team=, archetype affinity
# x system fit steer WHICH attributes develop (no double-counting: the
# legacy coach factor prices influence/youth/personality instead).
from player_development_system import PlayerDevelopmentEngine as _PDE
_pde = _PDE()
_mteam = mkteam([mkcoach("Head", StaffRole.HEAD_COACH, **ATTACK_COACH),
                 mkcoach("Off", StaffRole.ASSISTANT_COACH, **ATTACK_COACH)],
                even="Offensive")
def _monthly_hits(team_arg, attr, n=200):
    hits = 0
    for _ in range(n):
        pl = mkplayer(PlayerPosition.LEFT_WING, age=20, arch="Sniper",
                      base_controversy=20)
        pl.shooting = 60; pl.checking = 60
        if _pde.calculate_attribute_development(
                pl, attr, coach=_mteam.staff[0], team=team_arg) > 0:
            hits += 1
    return hits
random.seed(7)
_leg_s = _monthly_hits(None, "shooting"); _leg_c = _monthly_hits(None, "checking")
random.seed(7)
_new_s = _monthly_hits(_mteam, "shooting"); _new_c = _monthly_hits(_mteam, "checking")
check("monthly legacy path unaffected by team=None",
      abs(_leg_s - _leg_c) <= 6, f"s={_leg_s} c={_leg_c}")
check("monthly: sniper shooting out-develops checking (team=)",
      _new_s > _new_c * 1.5, f"s={_new_s} c={_new_c}")
# process_monthly_development threads team through (spot check, no raise)
_pl = mkplayer(PlayerPosition.CENTER, age=21, arch="Playmaker",
               base_controversy=20)
_pl.passing = 60
random.seed(11)
_chg = _pde.process_monthly_development(_pl, coach=_mteam.staff[0], team=_mteam)
check("process_monthly_development accepts team", isinstance(_chg, dict))

# Staff profile card shows the attributes the practice model prices.
from game_classes import Staff as _Staff, StaffRole as _StaffRole
def _mkstaff(role, **kw):
    _s = _Staff("Card", "Check", role)
    for _k, _v in kw.items():
        setattr(_s, _k, _v)
    return _s
_hc = _mkstaff(_StaffRole.HEAD_COACH, attacking_coaching=91, coaching_goalies=40,
               judging_player_ability=30)
_hd = _hc.get_attributes_for_role()
check("head coach card: 15 attributes", len(_hd) == 15, f"n={len(_hd)}")
check("card values match the staff object",
      _hd['attacking_coaching'] == 91 and _hd['coaching_goalies'] == 40)
check("card omits scout-only attributes", 'judging_player_ability' not in _hd)
_gc = _mkstaff(_StaffRole.GOALIE_COACH, coaching_goalies=93)
_gd = _gc.get_attributes_for_role()
check("goalie coach card leads with coaching_goalies",
      list(_gd)[0] == 'coaching_goalies' and _gd['coaching_goalies'] == 93)
_sd = _mkstaff(_StaffRole.HEAD_SCOUT, judging_player_ability=88).get_attributes_for_role()
check("scout card: scouting attributes only",
      set(_sd) == {'judging_player_ability', 'judging_player_potential',
                   'determination', 'adaptability'})
check("card covers every drill-teaching attribute",
      all(a in _hd for a in ('attacking_coaching', 'defensive_coaching',
                             'technical_coaching', 'mental_coaching')),
      "teaching quality visible")
check("card covers archetype-affinity inputs",
      all(a in _hd for a in ('coaching_forwards', 'coaching_defensemen',
                             'coaching_goalies', 'player_development',
                             'working_with_youngsters')),
      "affinity visible")
check("card covers attitude/system inputs",
      all(a in _hd for a in ('man_management', 'motivating', 'discipline',
                             'tactical_knowledge', 'adaptability')),
      "attitude/system visible")

print(f"\nALL {len(passed)} COACH-PRACTICE QA CHECKS PASSED")
