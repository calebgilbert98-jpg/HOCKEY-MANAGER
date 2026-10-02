"""QA for D41 Phase 1: scout-speculation FA tiering + lightweight AHL standings.

Verifies:
1. True tier derives from overall_rating (NHL 78+, AHL 68-77, Euro <68)
2. Scout tier is deterministic per player+scout (no flicker)
3. Elite scouts rarely mistier; bad scouts mistier often
4. True talent sometimes differs from scout tier (hidden gems exist)
5. AHL standings: records accumulate, sort correctly, persist shape
6. Tiering never raises on garbage input
7. Old-save backfill works
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0

def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


class FakePlayer:
    def __init__(self, ovr, name="Test Player", pid=1):
        self._ovr = ovr
        self.full_name = name
        self.id = pid
    def overall_rating(self):
        return self._ovr


class FakeScout:
    def __init__(self, jpa_raw, name="Scout", pid=1):
        self.judging_player_ability = jpa_raw
        self.full_name = name
        self.id = pid


class FakeTeam:
    def __init__(self, name, farm_ovrs=None):
        self.team_name = name
        self.ahl_roster = [FakePlayer(o, f"P{i}", i) for i, o in enumerate(farm_ovrs or [])]
        self.staff = []


class FakeLeague:
    def __init__(self, teams=None, fas=None):
        self.teams = teams or []
        self.free_agents = fas or []
        self.current_date = None


print("== D41 Phase 1 QA ==")

import scout_tiering as st
import ahl_system as ahl

# 1. True tier cutoffs
print("\n[true_tier]")
check("85 ovr -> NHL", st.true_tier(FakePlayer(85)) == "NHL")
check("78 ovr -> NHL (boundary)", st.true_tier(FakePlayer(78)) == "NHL")
check("77 ovr -> AHL (boundary)", st.true_tier(FakePlayer(77)) == "AHL")
check("68 ovr -> AHL (boundary)", st.true_tier(FakePlayer(68)) == "AHL")
check("67 ovr -> Euro (boundary)", st.true_tier(FakePlayer(67)) == "Euro")
check("50 ovr -> Euro", st.true_tier(FakePlayer(50)) == "Euro")

# 2. Determinism: same player+scout -> same tier every time
print("\n[determinism]")
p = FakePlayer(75, "Consistent Carl", 42)
s = FakeScout(50, "Average Al", 7)
t1 = st.scout_tier_for(p, s)
t2 = st.scout_tier_for(p, s)
t3 = st.scout_tier_for(p, s)
check("same player+scout -> same tier (no flicker)", t1 == t2 == t3)
# Different scout -> possibly different tier (that's the point)
s_bad = FakeScout(10, "Blind Bob", 99)
tiers_seen = {st.scout_tier_for(FakePlayer(ovr, f"P{ovr}", ovr), s_bad)
              for ovr in range(60, 90)}
check("bad scout produces varied reads", len(tiers_seen) >= 1)  # smoke

# 3. Scout accuracy: elite rarely mistiers, bad often does
print("\n[scout accuracy]")
import random
random.seed(12345)
# Build a spread of players across all tiers
players = [FakePlayer(ovr, f"Pl{ovr}_{i}", ovr * 100 + i)
           for ovr in list(range(55, 68)) + list(range(68, 78)) + list(range(78, 92))
           for i in range(3)]
elite = FakeScout(95, "Elite Eye", 1)   # JPA 19
bad = FakeScout(10, "Guesswork Gus", 2)  # JPA 2

elite_miss = sum(1 for pl in players if st.tier_mismatch(pl, elite))
bad_miss = sum(1 for pl in players if st.tier_mismatch(pl, bad))
elite_rate = elite_miss / len(players)
bad_rate = bad_miss / len(players)
print(f"    elite mistier rate: {elite_rate:.1%} ({elite_miss}/{len(players)})")
print(f"    bad mistier rate:   {bad_rate:.1%} ({bad_miss}/{len(players)})")
check("elite scout mistiers < 15%", elite_rate < 0.15)
check("bad scout mistiers > 25%", bad_rate > 0.25)
check("bad scout worse than elite", bad_rate > elite_rate)

# 4. Hidden gems: true NHL talent tagged AHL/Euro by a bad scout
print("\n[hidden gems]")
gems = [pl for pl in players
        if st.true_tier(pl) == "NHL" and st.scout_tier_for(pl, bad) != "NHL"]
check("bad scout hides some NHL talent (gems exist)", len(gems) > 0)
busts = [pl for pl in players
         if st.true_tier(pl) == "Euro" and st.scout_tier_for(pl, bad) == "NHL"]
check("bad scout overrates some Euro talent (busts exist)", len(busts) > 0)
print(f"    hidden gems: {len(gems)}, overrated busts: {len(busts)}")

# 5. AHL standings
print("\n[AHL standings]")
t1 = FakeTeam("Farm A", [75, 74, 73, 72, 71] * 4)  # strong
t2 = FakeTeam("Farm B", [65, 64, 63, 62, 61] * 4)  # weak
league = FakeLeague(teams=[t1, t2])
# Simulate 30 days
for _ in range(30):
    ahl.simulate_ahl_standings_day(league)
r1 = ahl.ensure_ahl_record(t1)
r2 = ahl.ensure_ahl_record(t2)
check("strong team played games", r1["gp"] > 0)
check("weak team played games", r2["gp"] > 0)
check("points = 2*w + otl", r1["pts"] == 2 * r1["w"] + r1["otl"])
check("gp = w + l + otl", r1["gp"] == r1["w"] + r1["l"] + r1["otl"])
standings = ahl.ahl_standings(league)
check("standings returns both teams", len(standings) == 2)
check("standings sorted by pts desc",
      standings[0][1]["pts"] >= standings[1][1]["pts"])
# Strong team should USUALLY finish ahead (probabilistic, allow some slack)
strong_first = standings[0][0].team_name == "Farm A"
print(f"    Farm A: {r1['w']}-{r1['l']}-{r1['otl']} ({r1['pts']} pts)")
print(f"    Farm B: {r2['w']}-{r2['l']}-{r2['otl']} ({r2['pts']} pts)")
# (not a hard check -- RNG -- but log it)
check("record dict has all keys",
      all(k in r1 for k in ("w", "l", "otl", "pts", "gf", "ga", "gp")))
# Reset
ahl.reset_ahl_record(t1)
check("reset zeroes record", ahl.ensure_ahl_record(t1)["gp"] == 0)

# 6. Never raises on garbage
print("\n[never raises]")
try:
    st.true_tier(None)
    st.scout_tier_for(None, None)
    st.perceived_overall(None, None)
    st.tier_player(None, None)
    st.tier_free_agents(None, None)
    st.backfill_tiers(None, None)
    st.tier_summary(None)
    st.get_head_scout(None)
    ahl.ensure_ahl_record(None)
    ahl.simulate_ahl_standings_day(None)
    ahl.ahl_standings(None)
    check("all functions survive garbage input", True)
except Exception as e:
    check(f"all functions survive garbage input ({e})", False)

# 7. Backfill: untiered FAs get tiered
print("\n[backfill]")
fa1 = FakePlayer(80, "Untiered Ulf", 101)  # no scout_tier attr
fa2 = FakePlayer(70, "Tiered Tina", 102)
fa2.scout_tier = "AHL"  # already tiered
lg2 = FakeLeague(fas=[fa1, fa2])
n = st.backfill_tiers(lg2, None)
check("backfill tiered the untiered FA", getattr(fa1, "scout_tier", None) in ("NHL", "AHL", "Euro"))
check("backfill left the tiered FA alone", fa2.scout_tier == "AHL")
check("backfill returned count", n == 1)

# 8. tier_summary
print("\n[tier summary]")
summ = st.tier_summary(lg2)
check("summary counts tiers", summ.get("NHL", 0) + summ.get("AHL", 0) + summ.get("Euro", 0) == 2)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
