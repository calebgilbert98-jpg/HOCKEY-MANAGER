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

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)