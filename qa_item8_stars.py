"""QA: Item 8 -- season star counts feed awards / reputation / development.

Controlled star counts:
  (i)   young player with many stars -> breakout nudge fires
  (ii)  veteran with many stars -> peak effect (decline resisted, never flipped)
  (iii) no stars -> zero effect from the new terms (existing behavior unchanged)
  (iv)  award-race ordering shifts appropriately with stars, all else equal
Plus: reputation star term is bounded; monthly deltas don't double-count;
the season ledger resets on League.end_of_season().
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# QA seed rule: pin BEFORE any generation (Player construction uses global RNG).
random.seed(20260929)

import awards_race as ar
import reputation_system as rs
import star_development as sd
import stars
from game_classes import League, Player, PlayerPosition, Team

passed, failed = 0, 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name} {detail}")


def skater(name, age, goals=20, assists=30, gp=60, pos=PlayerPosition.CENTER):
    p = Player(name, "Test", age, pos, 85)
    p.goals = goals
    p.assists = assists
    p.games_played = gp
    p.team_name = "Team A"
    p.leadership = 50
    p.captaincy = None
    return p


# ------------------------------------------------- (i) young breakout ---
print("== young breakout ==")
young = skater("Young", 21)
young.game_stars = {"first": 2, "second": 1, "third": 0}
_yattrs = [a for a in sd._SKATER_DEVELOPABLE if hasattr(young, a)]
before = {a: getattr(young, a) for a in _yattrs}
random.seed(7)  # pin before the sampled nudge
chg = sd.apply_star_monthly_nudge(young, {})
check("young: nudge fires with 2+ stars", sum(chg.values()) == 3, chg)
check("young: three attrs +1", all(v == 1 for v in chg.values()), chg)
check("young: attrs actually rose",
      all(getattr(young, a) == before[a] + chg[a] for a in chg))

# exactly one star: below threshold -> no-op
young2 = skater("Young2", 21)
young2.game_stars = {"first": 1, "second": 0, "third": 0}
random.seed(7)
check("young: 1 star is below threshold", sd.apply_star_monthly_nudge(young2, {}) == {})

# ------------------------------------------------- (ii) veteran peak ---
print("== veteran peak ==")
vet = skater("Vet", 34)
vet.game_stars = {"first": 2, "second": 0, "third": 0}
sk_before = vet.skating
sh_before = vet.shooting
random.seed(7)
chg = sd.apply_star_monthly_nudge(vet, {"skating": -2, "shooting": -1})
check("vet: decline softened by 1 per attr", chg == {"skating": 1, "shooting": 1}, chg)
check("vet: attrs restored", vet.skating == sk_before + 1 and vet.shooting == sh_before + 1)
# merged with the engine's changes, a -1 decline flattens to 0 (never flips +)
merged = {"skating": -2, "shooting": -1}
for a, c in chg.items():
    merged[a] += c
check("vet: -2 -> -1, -1 -> 0 (no positive flip)",
      merged == {"skating": -1, "shooting": 0}, merged)

# prime-age player: no effect by design
prime = skater("Prime", 28)
prime.game_stars = {"first": 5, "second": 0, "third": 0}
random.seed(7)
check("prime age (28): no star dev effect", sd.apply_star_monthly_nudge(prime, {"skating": -1}) == {})

# ------------------------------------------------- (iii) no stars -> zero effect ---
print("== no stars = zero effect ==")
nostar_y = skater("NoStarY", 21)
random.seed(7)
check("dev: young, no game_stars -> {}", sd.apply_star_monthly_nudge(nostar_y, {}) == {})
nostar_v = skater("NoStarV", 34)
sk = nostar_v.skating
random.seed(7)
check("dev: vet, no game_stars -> {}", sd.apply_star_monthly_nudge(nostar_v, {"skating": -2}) == {})
check("dev: vet attrs untouched", nostar_v.skating == sk)

a = skater("A", 25, goals=40, assists=60, gp=82)
b = skater("B", 25, goals=40, assists=60, gp=82)
team_pct = {"Team A": 0.600}
ra = ar.hart_race([a, b], team_pct)
expected = (100 + 0.4 * 40) * (0.75 + 0.5 * min(1.0, max(0.0, (0.600 - 0.400) / 0.250)))
check("race: no stars -> old formula exactly",
      abs(ra[0]["score"] - expected) < 1e-9, (ra[0]["score"], expected))
check("race: identical players tie without stars",
      abs(ra[0]["score"] - ra[1]["score"]) < 1e-9)

p0 = skater("Rep0", 25)
p0.reputation = 0
r0 = rs.update_player_reputation(p0, season_points=60, games_played=82,
                                 league_avg_ppg=0.9, awards=[], playoff_rounds_won=0)
check("rep: no stars -> perf(36) + leadership(5) = 41", r0 == 41, r0)

# -------------------------------------- (iv) award race shifts with stars ---
print("== award race ordering ==")
star = skater("Star", 25, goals=35, assists=62, gp=82)   # 97 pts
star.game_stars = {"first": 20, "second": 0, "third": 0}  # 20 weighted -> +8%
plain = skater("Plain", 25, goals=40, assists=60, gp=82)  # 100 pts, no stars
race = ar.hart_race([star, plain], team_pct)
check("hart: 20 weighted stars flip 97pts over 100pts",
      race[0]["player"] is star, [r["player"].first_name for r in race])
star.game_stars = {"first": 0, "second": 0, "third": 0}
race = ar.hart_race([star, plain], team_pct)
check("hart: same players, stars removed -> plain leads",
      race[0]["player"] is plain)

# bonus is scale-proportional: same pct on a small race score
r1 = skater("R1", 25, goals=30, assists=30, gp=82)
r1.game_stars = {"first": 10, "second": 0, "third": 0}
r2 = skater("R2", 25, goals=30, assists=30, gp=82)
s1 = ar.art_ross_race([r1], min_gp=20)[0]["score"]
s2 = ar.art_ross_race([r2], min_gp=20)[0]["score"]
check("art ross: 10 weighted stars = +4% of score",
      abs(s1 - s2 * 1.04) < 1e-9, (s1, s2))

# ------------------------------------------------- (b) reputation term ---
print("== reputation star term ==")
pr = skater("RepStar", 25)
pr.reputation = 0
rs.update_player_reputation(pr, season_points=60, games_played=82,
                            league_avg_ppg=0.9, awards=[], playoff_rounds_won=0)
pr.game_stars = {"first": 10, "second": 0, "third": 0}   # 10 * 0.4 = 4
r1 = rs.update_player_reputation(pr, season_points=60, games_played=82,
                                 league_avg_ppg=0.9, awards=[], playoff_rounds_won=0)
check("rep: 10 first-stars bank +4", r1 - 41 == 4, r1)

pr2 = skater("RepCap", 25)
pr2.reputation = 0
rs.update_player_reputation(pr2, season_points=60, games_played=82,
                            league_avg_ppg=0.9, awards=[], playoff_rounds_won=0)
pr2.game_stars = {"first": 100, "second": 0, "third": 0}  # 100 * 0.4 -> capped at 8
r2 = rs.update_player_reputation(pr2, season_points=60, games_played=82,
                                 league_avg_ppg=0.9, awards=[], playoff_rounds_won=0)
check("rep: star term hard-capped at +8", r2 - 41 == 8, r2)

# ------------------------------------------------- monthly delta hygiene ---
print("== monthly delta hygiene ==")
m = skater("M", 21)
m.game_stars = {"first": 3, "second": 0, "third": 0}
random.seed(11)
c1 = sd.apply_star_monthly_nudge(m, {})
random.seed(11)
c2 = sd.apply_star_monthly_nudge(m, {})  # no new stars since last tick
check("monthly: second tick with no new stars -> no-op",
      c2 == {} and sum(c1.values()) == 3, (c1, c2))
# season rollover: snapshot ahead of a zeroed ledger -> delta from fresh ledger
m.game_stars = {"first": 0, "second": 0, "third": 0}
random.seed(11)
check("monthly: post-rollover ledger -> no phantom stars",
      sd.apply_star_monthly_nudge(m, {}) == {})

# ------------------------------------------------- ledger reset on rollover ---
print("== season ledger reset ==")
lg = League(league_name="Item8 League")
t = Team(team_name="Item8 Team", city="Test", division="X", conference="Y")
lg.teams = [t]
lg.season_year = 2026
p = skater("Ledger", 25)
p.game_stars = {"first": 12, "second": 5, "third": 3}
t.roster.append(p)
lg.end_of_season()
check("end_of_season resets game_stars",
      p.game_stars == {"first": 0, "second": 0, "third": 0}, p.game_stars)

# weighted_star_count helper sanity
h = skater("H", 25)
h.game_stars = {"first": 2, "second": 2, "third": 4}
check("weighted count = 2 + 1 + 1",
      abs(stars.weighted_star_count(h) - 4.0) < 1e-9, stars.weighted_star_count(h))
h2 = skater("H2", 25)
check("no game_stars attr -> 0.0", stars.weighted_star_count(h2) == 0.0)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
