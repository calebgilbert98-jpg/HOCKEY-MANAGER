"""QA for the prospect development / farm production system.

Deterministic scenarios (seeded RNG) + a multi-year prospect census:
- league assignment by age/nationality
- hidden true potential vs displayed belief (gem seeding, scout reveal)
- NHLe normalization sanity
- breakout/bust evaluation from farm production
- development environment factor bounds and behavior
- age_one_year integration (default = old behavior)
- multi-year census: gems develop faster; late-rounders can climb
"""
import random
import sys

sys.path.insert(0, ".")
import prospect_development as pd
from game_classes import Player, PlayerPosition, PlayerStats

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else FAIL and 'FAIL'}: {name}" +
          (f" -- {detail}" if detail and not cond else ""))


def make_player(age=18, overall_target=66, grade="C", pos=PlayerPosition.CENTER,
                nationality="Canada", seed=0):
    # Pin global RNG too: Player construction fills unset attributes from it.
    random.seed(seed)
    rng = random.Random(seed)
    p = Player(first_name="Test", last_name=f"P{seed}", age=age,
               primary_position=pos)
    p.nationality = nationality
    p.potential_grade = grade
    p.true_potential_grade = grade
    # Flatten attributes toward the target overall-ish level
    for attr in ("skating", "shooting", "passing", "hockey_iq", "strength",
                 "checking", "defense"):
        if hasattr(p, attr):
            setattr(p, attr, max(1, min(99, overall_target + rng.randint(-4, 4))))
    p.morale = 70
    return p


# --- 1. League assignment -------------------------------------------------
p = make_player(age=18, nationality="Canada")
check("assign: 18yo Canadian -> CHL",
      pd.assign_prospect_league(p) in ("OHL", "WHL", "QMJHL"))
p = make_player(age=18, nationality="USA")
check("assign: 18yo American -> USHL", pd.assign_prospect_league(p) == "USHL")
p = make_player(age=19, nationality="USA")
check("assign: 19yo American -> NCAA", pd.assign_prospect_league(p) == "NCAA")
p = make_player(age=18, nationality="Sweden")
check("assign: 18yo Swede -> SHL", pd.assign_prospect_league(p) == "SHL")
p = make_player(age=18, nationality="Finland")
check("assign: 18yo Finn -> Liiga", pd.assign_prospect_league(p) == "Liiga")
p = make_player(age=22, nationality="Canada")
check("assign: 22yo -> AHL", pd.assign_prospect_league(p) == "AHL")
p = make_player(age=18, nationality="Canada")
check("assign: explicit AHL respected",
      pd.assign_prospect_league(p, "AHL") == "AHL")

# --- 2. Season sim stores sane data ----------------------------------------
rng = random.Random(7)
p = make_player(age=18, overall_target=70, grade="B")
s = pd.simulate_prospect_season(p, league="OHL", rng=rng)
check("sim: stores league", p.farm_league == "OHL")
check("sim: season has gp/pts", s["gp"] > 40 and s["pts"] >= 0)
check("sim: ppg consistent", abs(s["ppg"] - s["pts"] / s["gp"]) < 0.01)
check("sim: history appended", len(p.farm_history) == 1)
# Elite kid should dominate junior
check("sim: elite 18yo scores (ppg>0.8)", s["ppg"] > 0.8, f"ppg={s['ppg']}")
# Weaker kid scores less than the elite kid (monotonic in skill)
p2 = make_player(age=18, overall_target=52, grade="D", seed=3)
s2 = pd.simulate_prospect_season(p2, league="OHL", rng=random.Random(7))
check("sim: weak kid < elite kid", s2["ppg"] < s["ppg"],
      f"weak={s2['ppg']} elite={s['ppg']}")

# Goalie sim
g = make_player(age=19, overall_target=66, grade="B", pos=PlayerPosition.GOALIE,
                seed=5)
gs = pd.simulate_prospect_season(g, league="AHL", rng=random.Random(11))
check("sim: goalie has sv_pct", 0.84 < gs["sv_pct"] < 0.945,
      f"sv={gs['sv_pct']}")

# History capped at 6
for i in range(8):
    pd.simulate_prospect_season(p, league="OHL", rng=random.Random(i))
check("sim: history capped at 6", len(p.farm_history) == 6)

# --- 3. NHLe normalization -------------------------------------------------
# Same PPG in KHL must be worth far more than in the USHL.
p = make_player(age=20, overall_target=70, seed=9)
p.farm_season = {"league": "KHL", "gp": 60, "g": 20, "a": 40, "pts": 60,
                 "ppg": 1.0}
khl = pd.farm_nhle_ppg(p)
p.farm_season = {"league": "USHL", "gp": 60, "g": 20, "a": 40, "pts": 60,
                 "ppg": 1.0}
ushl = pd.farm_nhle_ppg(p)
check("nhle: KHL ppg > USHL ppg", khl > ushl * 2.5, f"{khl} vs {ushl}")
check("nhle: KHL factor ~0.83", abs(khl - 0.83) < 0.01, f"{khl}")

# --- 4. Gem seeding ---------------------------------------------------------
rng = random.Random(1234)
bumps = 0
displayed_kept = True
for i in range(2000):
    q = make_player(age=18, overall_target=60, grade="D", seed=1000 + i)
    q.true_potential_grade = ""  # force seeding
    pd.seed_true_potential(q, draft_round=7, rng=rng)
    if q.true_potential_grade != "D":
        bumps += 1
    if q.potential_grade != "D":
        displayed_kept = False
check("gem: late rounds produce hidden bumps", 150 < bumps < 400,
      f"bumps={bumps}/2000")
check("gem: displayed grade untouched", displayed_kept)
# Early picks rarely bumped
bumps1 = 0
rng = random.Random(1234)
for i in range(2000):
    q = make_player(age=18, overall_target=72, grade="B", seed=2000 + i)
    q.true_potential_grade = ""
    pd.seed_true_potential(q, draft_round=1, rng=rng)
    if q.true_potential_grade != "B":
        bumps1 += 1
check("gem: 1st round rarely bumped", bumps1 < 100, f"{bumps1}/2000")
# Idempotent
q = make_player(age=18, grade="D", seed=42)
q.true_potential_grade = ""
pd.seed_true_potential(q, draft_round=7, rng=random.Random(1))
first = q.true_potential_grade
pd.seed_true_potential(q, draft_round=7, rng=random.Random(999))
check("gem: seeding idempotent", q.true_potential_grade == first)

# --- 5. _potential_cap follows truth ---------------------------------------
q = make_player(age=18, overall_target=62, grade="D", seed=77)
q.true_potential_grade = "B"
check("cap: true B -> cap 82 (not D's 69)", q._potential_cap() == 82,
      f"cap={q._potential_cap()}")
q.true_potential_grade = ""
check("cap: old-save fallback to displayed", q._potential_cap() == 69,
      f"cap={q._potential_cap()}")

# --- 6. Breakout / bust evaluation ------------------------------------------
# Elite farm season for a D(displayed)/B(true) 18yo gem
def elite_season(p, ppg, league="OHL", gp=60):
    pts = int(ppg * gp)
    p.farm_season = {"league": league, "gp": gp, "g": pts // 3,
                     "a": pts - pts // 3, "pts": pts, "ppg": ppg}
    p.farm_history = [dict(p.farm_season)]

trials = 300
breakouts = noticed = 0
for i in range(trials):
    q = make_player(age=18, overall_target=70, grade="D", seed=5000 + i)
    q.true_potential_grade = "B"
    elite_season(q, 1.9, gp=62)  # dominant: NHLe ~0.53-0.57, clears bar
    r = pd.evaluate_prospect_season(q, rng=random.Random(i))
    if r == "breakout":
        breakouts += 1
    if r == "noticed" or q.potential_grade != "D":
        noticed += 1
check("eval: dominant gem breaks out sometimes", breakouts > trials * 0.15,
      f"{breakouts}/{trials}")
check("eval: loud production moves belief", noticed > trials * 0.4,
      f"{noticed}/{trials}")

# Bust: touted prospect, terrible production
busts = 0
for i in range(trials):
    q = make_player(age=21, overall_target=64, grade="B", seed=6000 + i)
    q.true_potential_grade = "B"
    elite_season(q, 0.15, league="AHL", gp=55)  # NHLe 0.066 < bust bar
    r = pd.evaluate_prospect_season(q, rng=random.Random(10000 + i))
    if r == "bust":
        busts += 1
check("eval: terrible touted prospect busts sometimes", busts > trials * 0.1,
      f"{busts}/{trials}")

# Small sample: no judgement
q = make_player(age=18, overall_target=70, grade="D", seed=1)
elite_season(q, 2.2, gp=8)
check("eval: tiny sample -> None", pd.evaluate_prospect_season(q) is None)
# Old: no judgement
q = make_player(age=28, overall_target=70, grade="C", seed=2)
elite_season(q, 1.5, gp=60)
check("eval: age 28 -> None", pd.evaluate_prospect_season(q) is None)

# --- 7. Environment factor ---------------------------------------------------
p = make_player(age=18, overall_target=70, grade="B", seed=21)
p.farm_league = "OHL"
p.morale = 85
f = pd.development_environment_factor(p)
check("env: ideal 18yo > 1.2", f > 1.2, f"f={f}")
p2 = make_player(age=25, overall_target=70, grade="C", seed=22)
p2.farm_league = "AHL"
p2.morale = 55
f2 = pd.development_environment_factor(p2)
check("env: 25yo grinder < ideal teen", f2 < f, f"f2={f2}")
check("env: bounded [0.70, 1.50]",
      all(0.70 <= pd.development_environment_factor(
          make_player(age=a, overall_target=o, grade="C", seed=a * 31 + o),
          league=l) <= 1.50
          for a in (17, 20, 23, 26) for o in (55, 75, 90)
          for l in ("OHL", "KHL", "AHL", "NCAA", "NHL")))
# Generational damping: A+ teen factor closer to 1.0 than a B teen's
gen = make_player(age=18, overall_target=80, grade="A+", seed=30)
gen.true_potential_grade = "A+"
gen.farm_league = "OHL"
gen.morale = 85
gf = pd.development_environment_factor(gen)
check("env: generational damped toward 1.0", abs(gf - 1.0) < abs(f - 1.0),
      f"gen={gf} vs b={f}")
# NHL rookie gets the steroid treatment too
rk = make_player(age=20, overall_target=74, grade="B", seed=31)
rk.morale = 80
rf = pd.development_environment_factor(rk, league="NHL")
check("env: NHL rookie boosted", rf > 1.1, f"rf={rf}")
# Veteran untouched
vt = make_player(age=30, overall_target=78, grade="B", seed=32)
check("env: veteran factor = 1.0",
      pd.development_environment_factor(vt, league="NHL") == 1.0)

# --- 8. age_one_year default unchanged ---------------------------------------
a = make_player(age=19, overall_target=66, grade="B", seed=40)
b = make_player(age=19, overall_target=66, grade="B", seed=40)
random.seed(99)
oa = a.overall_rating()
a.age_one_year()  # default env_factor=1.0
random.seed(99)
b.age_one_year(env_factor=1.0)
check("age: default factor == old behavior",
      a.overall_rating() == b.overall_rating())
# env factor > 1 grows more
c = make_player(age=19, overall_target=66, grade="B", seed=40)
random.seed(99)
c.age_one_year(env_factor=1.5)
check("age: env 1.5 grows >= env 1.0",
      c.overall_rating() >= a.overall_rating())

# --- 9. scout reveal ----------------------------------------------------------
lo_jpp_hits = hi_jpp_hits = 0
for i in range(400):
    q = make_player(age=18, overall_target=62, grade="D", seed=7000 + i)
    q.true_potential_grade = "B"
    if pd.scout_reveal_step(q, scout_jpp=92, rng=random.Random(i)):
        hi_jpp_hits += 1
    q2 = make_player(age=18, overall_target=62, grade="D", seed=7000 + i)
    q2.true_potential_grade = "B"
    if pd.scout_reveal_step(q2, scout_jpp=45, rng=random.Random(i)):
        lo_jpp_hits += 1
check("scout: elite scout reveals more", hi_jpp_hits > lo_jpp_hits * 1.5,
      f"hi={hi_jpp_hits} lo={lo_jpp_hits}")
# Already-known truth: no-op
q = make_player(age=18, grade="B", seed=1)
q.true_potential_grade = "B"
check("scout: no-op when known",
      pd.scout_reveal_step(q, scout_jpp=95) is False)

# --- 10. callup readiness ------------------------------------------------------
star = make_player(age=21, overall_target=80, grade="A-", seed=50)
star.farm_history = [{"league": "AHL", "gp": 70, "g": 25, "a": 40,
                      "pts": 65, "ppg": 0.93}]
grinder = make_player(age=24, overall_target=68, grade="C", seed=51)
grinder.farm_history = [{"league": "AHL", "gp": 70, "g": 8, "a": 12,
                         "pts": 20, "ppg": 0.29}]
check("readiness: star > grinder",
      pd.callup_readiness(star) > pd.callup_readiness(grinder),
      f"{pd.callup_readiness(star)} vs {pd.callup_readiness(grinder)}")
check("readiness: bounded 0-100",
      0 <= pd.callup_readiness(grinder) <= 100)

# --- 11. Multi-year census ------------------------------------------------------
# 60 prospects, 5 offseasons: gems (true>displayed) must out-develop
# same-displayed peers; some late-rounders must climb the ladder.
rng = random.Random(2026)
census = []
for i in range(60):
    grade = rng.choice(["B", "C", "D", "D", "C", "D"])
    q = make_player(age=18, overall_target=rng.randint(58, 68), grade=grade,
                    seed=9000 + i,
                    nationality=rng.choice(["Canada", "USA", "Sweden"]))
    q.true_potential_grade = ""
    pd.seed_true_potential(q, draft_round=rng.randint(2, 7), rng=rng)
    q._gem = q.true_potential_grade != q.potential_grade
    q._start_ovr = q.overall_rating()
    q._start_disp = q.potential_grade
    census.append(q)

for year in range(5):
    for q in census:
        pd.process_prospect_offseason(q, rng=rng)
        q.age_one_year(env_factor=pd.development_environment_factor(q))

gems = [q for q in census if q._gem]
non_gems = [q for q in census if not q._gem
            and q.potential_grade in ("C", "D")]
gem_gain = sum(q.overall_rating() - q._start_ovr for q in gems) / max(len(gems), 1)
peer_gain = sum(q.overall_rating() - q._start_ovr for q in non_gems) / max(len(non_gems), 1)
check("census: hidden gems out-develop peers",
      gem_gain > peer_gain + 0.5,
      f"gems +{gem_gain:.1f} vs peers +{peer_gain:.1f} (n={len(gems)}/{len(non_gems)})")
climbers = sum(1 for q in census
               if pd._ladder_index(q.potential_grade) >
               pd._ladder_index(q._start_disp)
               and q._start_disp in ("C", "D", "D+", "C-"))
check("census: some late-rounders climb", climbers >= 3,
      f"climbers={climbers}")
check("census: no runaway overalls",
      all(q.overall_rating() <= 99 for q in census))
check("census: history capped", all(len(q.farm_history) <= 6 for q in census))

# --- 12. Pedigree cushion (the Lafreniere rule) -------------------------------
q = make_player(age=18, overall_target=72, grade="A", seed=8001)
q.true_potential_grade = ""
pd.seed_true_potential(q, draft_round=1, rng=random.Random(5))
check("pedigree: round-1 floor stamped",
      q.draft_round == 1 and q.pedigree_floor != "",
      f"round={q.draft_round} floor={q.pedigree_floor}")
q7 = make_player(age=18, overall_target=60, grade="D", seed=8002)
q7.true_potential_grade = ""
pd.seed_true_potential(q7, draft_round=7, rng=random.Random(5))
check("pedigree: round-7 no floor", q7.pedigree_floor == "")


def _bad_farm_season(p, league="AHL", gp=50):
    p.farm_season = {"league": league, "gp": gp, "g": 3, "a": 5,
                     "pts": 8, "ppg": 8 / gp}
    p.farm_history = [dict(p.farm_season)]


def prospect_bust_rate(draft_round, trials=400):
    n = 0
    for i in range(trials):
        qq = make_player(age=20, overall_target=64, grade="A-", seed=8100 + i)
        qq.true_potential_grade = ""
        pd.seed_true_potential(qq, draft_round=draft_round,
                               rng=random.Random(30000 + i))
        # Sit exactly on the floor (round 1) or at B (no floor)
        if draft_round == 1:
            qq.true_potential_grade = qq.pedigree_floor
            qq.potential_grade = qq.pedigree_floor
        else:
            qq.true_potential_grade = "B"
            qq.potential_grade = "B"
        _bad_farm_season(qq)
        r = pd.evaluate_prospect_season(qq, rng=random.Random(40000 + i))
        if r == "bust":
            n += 1
    return n


floored_busts = prospect_bust_rate(1)
open_busts = prospect_bust_rate(5)
check("pedigree: floor cushions busts (~1/4 rate)",
      floored_busts < open_busts * 0.5,
      f"floored={floored_busts} open={open_busts}")
check("pedigree: floor is soft not a wall (Yakupovs happen)",
      floored_busts > 0, f"floored={floored_busts}")


def nhl_bust_rate(floored, trials=400):
    n = 0
    for i in range(trials):
        qq = make_player(age=21, overall_target=68, grade="B-", seed=8300 + i)
        if floored:
            qq.true_potential_grade = "B-"
            qq.pedigree_floor = "B-"
            qq.draft_round = 1
        qq.stats = PlayerStats()
        qq.stats.games_played = 60
        qq.stats.goals = 6
        qq.stats.assists = 12  # 0.30 ppg < bust bar 0.35
        before = qq.potential_grade
        random.seed(50000 + i)
        qq.update_potential_from_season()
        if qq.potential_grade != before:
            n += 1
    return n


floored_nhl = nhl_bust_rate(True)
open_nhl = nhl_bust_rate(False)
check("pedigree: NHL busts cushioned too",
      floored_nhl < open_nhl * 0.6,
      f"floored={floored_nhl} open={open_nhl}")

# Hype cools: touted A+ kid, mediocre-not-terrible production
cooled = 0
for i in range(300):
    qq = make_player(age=18, overall_target=70, grade="A+", seed=8200 + i)
    qq.true_potential_grade = "A+"
    elite_season(qq, 0.95, gp=60)  # NHLe ~0.285: not bust, not elite-track
    r = pd.evaluate_prospect_season(qq, rng=random.Random(60000 + i))
    if r == "cooled":
        cooled += 1
check("hype: cools sometimes for touted elites", 30 < cooled < 200,
      f"cooled={cooled}/300")
# ...but the floor keeps them NHL-caliber
below_floor = 0
for i in range(300):
    qq = make_player(age=18, overall_target=70, grade="A+", seed=8400 + i)
    qq.true_potential_grade = ""
    pd.seed_true_potential(qq, draft_round=1, rng=random.Random(70000 + i))
    qq.true_potential_grade = "A-"  # already cooled once, at the floor
    qq.potential_grade = "A-"
    elite_season(qq, 0.95, gp=60)
    pd.evaluate_prospect_season(qq, rng=random.Random(80000 + i))
    if pd._ladder_index(qq.true_potential_grade) < pd._ladder_index("A-"):
        below_floor += 1
check("hype: floor holds at A- for 1st-overall shape (mostly)",
      below_floor < 60, f"below={below_floor}/300")

# League stickiness: no junior-league hopping year to year
q = make_player(age=18, overall_target=64, grade="C", seed=8600)
q.nationality = "Canada"
pd.simulate_prospect_season(q, rng=random.Random(1))
first = q.farm_league
leagues = {first}
for y in range(2):  # ages 19, 20: still junior-eligible
    q.age += 1
    pd.simulate_prospect_season(q, rng=random.Random(100 + y))
    leagues.add(q.farm_league)
check("sticky: junior stays in one league",
      first in ("OHL", "WHL", "QMJHL") and leagues == {first},
      f"leagues={sorted(leagues)}")
# ...but aging out still moves him up (junior -> AHL at 21)
q.age = 21
pd.simulate_prospect_season(q, rng=random.Random(2))
check("sticky: ages out to pro at 21", q.farm_league == "AHL",
      f"league={q.farm_league}")

# Old-save backfill for pedigree fields
import reputation_system as rs
old = make_player(age=20, overall_target=66, grade="B", seed=8500)
del old.true_potential_grade
del old.pedigree_floor
del old.draft_round
rs.ensure_reputation_fields(old)
check("backfill: pedigree fields set",
      old.true_potential_grade == "B" and old.pedigree_floor != "",
      f"true={old.true_potential_grade} floor={old.pedigree_floor}")



# --- 12. Situational readiness (multi-factor) ---------------------------
import types
import reputation_system as rs


def make_team(roster, staff=None, wins=30, losses=30, ot_losses=8):
    return types.SimpleNamespace(roster=list(roster), staff=list(staff or []),
                                 wins=wins, losses=losses, ot_losses=ot_losses)


def make_star(ovr=84, pos=PlayerPosition.CENTER, seed=900):
    s = make_player(age=28, overall_target=ovr, grade="A-", pos=pos, seed=seed)
    for attr in ("skating", "shooting", "passing", "hockey_iq", "strength",
                 "checking", "defense"):
        if hasattr(s, attr):
            setattr(s, attr, ovr)
    # Pin the number overall_rating() would otherwise dilute with the
    # player's other randomized attributes -- the tests need a known star.
    s.overall_rating = lambda _o=ovr: float(_o)
    return s


def get_delta(deltas, frag):
    return next((d for lab, d in deltas if frag in lab), None)


kid = make_player(age=21, overall_target=74, grade="B", seed=101)
base, d0 = pd.situational_readiness(kid, None)
check("sit: no team -> base score, no opportunity/coach deltas",
      all("door is open" not in lab and "Coach fit" not in lab
          for lab, _ in d0) and base == pd.callup_readiness(kid),
      f"base={base} deltas={d0}")

star = make_star()
team = make_team([star, kid])
s1, d1 = pd.situational_readiness(kid, team)
check("sit: healthy roster -> no opportunity bump",
      all("door is open" not in lab for lab, _ in d1), f"deltas={d1}")

star.is_injured = True
s2, d2 = pd.situational_readiness(kid, team)
opp = get_delta(d2, "door is open")
check("sit: star injured -> named major-piece bump",
      opp is not None and 2 <= opp <= 12 and "Major piece down" in
      next(lab for lab, _ in d2 if "door is open" in lab)
      and star.last_name in next(lab for lab, _ in d2 if "door is open" in lab),
      f"deltas={d2}")
check("sit: opportunity raises the number", s2 > s1, f"{s1} -> {s2}")

# The gap matters: a closer-to-the-star kid cashes more of the bump.
closer = make_player(age=23, overall_target=82, grade="B+", seed=111)
s_far, _ = pd.situational_readiness(kid, team)
s_close, _ = pd.situational_readiness(closer, team)
check("sit: nearer-the-hole kid gains more",
      (s_close - pd.callup_readiness(closer))
      > (s_far - pd.callup_readiness(kid)),
      f"far={s_far:.1f} close={s_close:.1f}")

# Line fit scaled by toolbox, not flat.
sniper = make_player(age=21, overall_target=74, grade="B", seed=102)
sniper.shooting = 90; sniper.hockey_iq = 80; sniper.checking = 55
grinder = make_player(age=21, overall_target=74, grade="B", seed=103)
grinder.checking = 90; grinder.strength = 85; grinder.shooting = 60
_, d_sn = pd.situational_readiness(sniper, team)
_, d_gr = pd.situational_readiness(grinder, team)
fit_sn = get_delta(d_sn, "Built for the")
check("sit: elite sniper owns the scorer hole",
      fit_sn is not None and fit_sn >= 3.0, f"{d_sn}")
check("sit: checker in scorer hole -> wrong role, negative",
      get_delta(d_gr, "Wrong role") is not None
      and get_delta(d_gr, "Wrong role") < 0, f"{d_gr}")

# Depth injury: smaller, humbler bump.
mid = make_star(ovr=75, seed=901); mid.is_injured = True
team2 = make_team([mid, closer])
_, d_mid = pd.situational_readiness(closer, team2)
mid_opp = get_delta(d_mid, "door is open")
_, d_star_close = pd.situational_readiness(closer, team)
star_opp = get_delta(d_star_close, "door is open")
check("sit: depth injury -> 'Regular down', smaller hole than star's",
      mid_opp is not None and star_opp is not None and mid_opp < star_opp
      and "Regular down" in next(lab for lab, _ in d_mid
                                 if "door is open" in lab),
      f"{d_mid}")

# Other position's injury does not open his door.
d_star = make_star(ovr=86, pos=PlayerPosition.DEFENSE, seed=902)
d_star.is_injured = True
team3 = make_team([d_star, kid])
_, d_d = pd.situational_readiness(kid, team3)
check("sit: D injury -> no bump for a forward",
      all("door is open" not in lab for lab, _ in d_d), f"{d_d}")

# Moment terms: the same hole, two different kids.
def kid_with(seed, **mentals):
    k = make_player(age=21, overall_target=74, grade="B", seed=seed)
    for a in ("skating", "shooting", "passing", "hockey_iq", "strength",
              "checking", "defense", "balance", "stamina", "off_the_puck",
              "vision"):
        if hasattr(k, a):
            setattr(k, a, 70)
    for m, v in mentals.items():
        if hasattr(k, m):
            setattr(k, m, v)
    k.overall_rating = lambda: 74.0
    return k

gamer = kid_with(201, composure=85, pressure_player=85, confidence=80,
                 morale=85, determination=85, work_ethic=85, consistency=85,
                 nhl_games_played=30)
shrinking = kid_with(202, composure=30, pressure_player=30, confidence=35,
                     morale=45, determination=40, work_ethic=40,
                     consistency=35, nhl_games_played=0)
s_gamer, d_gamer = pd.situational_readiness(gamer, team)
s_shrink, d_shrink = pd.situational_readiness(shrinking, team)
check("sit: same scenario, different kids -> different numbers",
      abs(s_gamer - s_shrink) >= 4.0,
      f"gamer={s_gamer} shrink={s_shrink}")
check("sit: gamer shows composure/temperament deltas",
      get_delta(d_gamer, "Composure") not in (None,)
      and get_delta(d_gamer, "Composure") > 0, f"{d_gamer}")
check("sit: true rookie takes the no-experience hit",
      get_delta(d_shrink, "Never played an NHL shift") == -2.0,
      f"{d_shrink}")

# Contract-year hunger and team situation.
hungry = kid_with(203, composure=60, pressure_player=50, morale=70,
                  confidence=60, determination=55, work_ethic=55,
                  consistency=55)
hungry.contract.years_remaining = 1
_, d_h = pd.situational_readiness(hungry, team)
check("sit: contract year -> hunger bump",
      get_delta(d_h, "Contract-year hunger") == 1.5, f"{d_h}")
team_cont = make_team([star, hungry], wins=48, losses=22, ot_losses=6)
_, d_c1 = pd.situational_readiness(hungry, team_cont)
check("sit: contender -> short leash",
      get_delta(d_c1, "short leash") == -2.0, f"{d_c1}")
team_reb = make_team([star, hungry], wins=20, losses=55, ot_losses=7)
_, d_c2 = pd.situational_readiness(hungry, team_reb)
check("sit: rebuild -> kids get runway",
      get_delta(d_c2, "runway") == 2.0, f"{d_c2}")

# Coach fit leg (monkeypatched response -- tests OUR wiring, not theirs).
coach = types.SimpleNamespace(id=7,
                              role=types.SimpleNamespace(value="Head Coach"))
team_c = make_team([kid], staff=[coach])
orig_resp = rs.player_coach_response
try:
    rs.player_coach_response = lambda pl, c: {"label": "Bought in"}
    _, d_bi = pd.situational_readiness(kid, team_c)
    rs.player_coach_response = lambda pl, c: {"label": "Quit on coach"}
    _, d_q = pd.situational_readiness(kid, team_c)
    rs.player_coach_response = lambda pl, c: {"label": "Neutral"}
    _, d_n = pd.situational_readiness(kid, team_c)
finally:
    rs.player_coach_response = orig_resp
check("sit: coach Bought in -> positive",
      get_delta(d_bi, "Coach fit") is not None
      and get_delta(d_bi, "Coach fit") > 0, f"{d_bi}")
check("sit: coach Quit on coach -> strongly negative",
      get_delta(d_q, "Coach fit") is not None
      and get_delta(d_q, "Coach fit") <= -8, f"{d_q}")
check("sit: coach Neutral -> no delta",
      all("Coach fit" not in lab for lab, _ in d_n), f"{d_n}")

# Farm trend: slope-scaled now.
trend = make_player(age=21, overall_target=74, grade="B", seed=104)
trend.farm_history = [{"league": "AHL", "ppg": 0.50},
                      {"league": "AHL", "ppg": 0.95}]
_, d_t = pd.situational_readiness(trend, None)
tr = get_delta(d_t, "Production trending up")
check("sit: steep rising trend -> near-max bump",
      tr is not None and 7.0 <= tr <= 8.0, f"{d_t}")
flat = make_player(age=21, overall_target=74, grade="B", seed=105)
flat.farm_history = [{"league": "AHL", "ppg": 0.70},
                     {"league": "AHL", "ppg": 0.72}]
_, d_f = pd.situational_readiness(flat, None)
check("sit: flat production -> no trend delta",
      all("trending" not in lab for lab, _ in d_f), f"{d_f}")

# Fast channel: the NHL audition.
aud = make_player(age=21, overall_target=74, grade="B", seed=106)
aud.nhl_audition = {"goals": 10, "assists": 12, "games_played": 40}
aud.goals, aud.assists, aud.games_played = 14, 16, 45  # 8 pts in 5 GP
s_a, d_a = pd.situational_readiness(aud, None)
check("sit: hot audition -> 'Showing he belongs'",
      get_delta(d_a, "Showing he belongs") is not None
      and get_delta(d_a, "Showing he belongs") >= 10.0,
      f"score={s_a} deltas={d_a}")
aud2 = make_player(age=21, overall_target=74, grade="B", seed=107)
aud2.nhl_audition = {"goals": 10, "assists": 12, "games_played": 40}
aud2.goals, aud2.assists, aud2.games_played = 10, 13, 48  # 1 pt in 8 GP
s_a2, d_a2 = pd.situational_readiness(aud2, None)
check("sit: cold audition -> 'Overmatched' -8",
      get_delta(d_a2, "Overmatched") == -8.0,
      f"score={s_a2} deltas={d_a2}")
aud3 = make_player(age=21, overall_target=74, grade="B", seed=108)
aud3.nhl_audition = {"goals": 10, "assists": 12, "games_played": 40}
aud3.goals, aud3.assists, aud3.games_played = 10, 12, 41  # only 1 game
_, d_a3 = pd.situational_readiness(aud3, None)
check("sit: tiny sample -> no audition judgement",
      all("belongs" not in lab and "Overmatched" not in lab
          for lab, _ in d_a3), f"{d_a3}")
# Heater: point streak on top of a solid audition.
aud4 = make_player(age=20, overall_target=74, grade="B", seed=109)
aud4.nhl_audition = {"goals": 0, "assists": 0, "games_played": 0}
aud4.goals, aud4.assists, aud4.games_played = 2, 3, 8
aud4.current_point_streak = 5
_, d_a4 = pd.situational_readiness(aud4, None)
check("sit: point streak adds the heater",
      get_delta(d_a4, "Riding a heater") == 2.0, f"{d_a4}")

# Goalie path: starter down -> goalie kid gets the bump.
gkid = make_player(age=22, overall_target=76, grade="B",
                   pos=PlayerPosition.GOALIE, seed=110)
gstar = make_star(ovr=88, pos=PlayerPosition.GOALIE, seed=903)
gstar.is_injured = True
team_g = make_team([gstar, gkid])
_, d_g = pd.situational_readiness(gkid, team_g)
check("sit: starter down -> goalie prospect bumped",
      get_delta(d_g, "door is open") is not None
      and get_delta(d_g, "door is open") > 0, f"{d_g}")

# Injured kid is not an option, period.
hurt = make_player(age=21, overall_target=80, grade="B", seed=111)
hurt.is_injured = True
s_hurt, d_hurt = pd.situational_readiness(hurt, team)
check("sit: injured kid -> 0, not an option",
      s_hurt == 0.0 and any("not an option" in lab for lab, _ in d_hurt),
      f"score={s_hurt}")

# Clamp: stacked good news never exceeds +32 of swing.
lucky = make_player(age=24, overall_target=88, grade="A", seed=112)
lucky.farm_history = [{"league": "AHL", "ppg": 0.5},
                      {"league": "AHL", "ppg": 1.4}]
lucky.nhl_audition = {"goals": 0, "assists": 0, "games_played": 0}
lucky.goals, lucky.assists, lucky.games_played = 6, 6, 10
star2 = make_star(ovr=90, seed=904); star2.is_injured = True
s_l, d_l = pd.situational_readiness(lucky, make_team([star2, lucky]))
swing = s_l - pd.callup_readiness(lucky)
check("sit: swing clamps at +/-32, score 0-100",
      0 <= s_l <= 100 and abs(swing) <= 32.5, f"score={s_l} swing={swing}")


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)