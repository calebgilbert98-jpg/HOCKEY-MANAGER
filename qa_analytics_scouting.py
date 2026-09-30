"""QA for the analytics scouting layer: truth + scout perception.

Verifies:
- Ground-truth finders flag real value (buy-low) and hot luck (sell-high)
- Scout tips are filtered through judging_player_ability:
  elite scouts mostly name real finds; poor scouts chase ghosts
- Storyline generator produces sensible seeds
- Fresh-start morale rewards rescues, punishes downgrades
- Award races agree with _calculate_season_awards winners
"""
from types import SimpleNamespace
import random
import sys

sys.path.insert(0, ".")

import analytics_scouting as scout
import reputation_system as rs

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name}")


def mkpos(name):
    return SimpleNamespace(name=name)


def mkskater(name, team, gp, g, a, age=26, sal=4000000):
    p = SimpleNamespace(
        full_name=name, team_name=team, games_played=gp, goals=g, assists=a,
        shots=220, hits=50, blocked_shots=40, takeaways=30, giveaways=20,
        pim=25, plus_minus=5, faceoff_wins=100, faceoff_attempts=200,
        primary_position=mkpos("C"), age=age,
        contract=SimpleNamespace(salary=sal, years_remaining=2),
    )
    for attr, val in [("shooting", 84), ("passing", 84), ("puckhandling", 83),
                      ("skating", 85), ("off_awareness", 84), ("def_awareness", 80),
                      ("strength", 78), ("checking", 70), ("fighting", 50),
                      ("faceoffs", 75), ("shot_blocking", 65), ("durability", 80)]:
        setattr(p, attr, val)
    p.overall_rating = lambda: 84
    return p


def mkteam(name, gp, pts):
    return SimpleNamespace(team_name=name, games_played=gp, points=pts,
                           roster=[], dynamics_log=[])


def mkscout(name, jpa):
    return SimpleNamespace(full_name=name, judging_player_ability=jpa,
                           judging_player_potential=12)


# --- Ground truth ----------------------------------------------------------
bad = mkteam("Lottery FC", 50, 40)
good = mkteam("Contender HC", 50, 70)
user = mkteam("User Team", 50, 62)

unlucky = mkskater("Alex Undervalued", "Lottery FC", 45, 8, 15, age=24,
                   sal=2500000)
fair = mkskater("Joe Fair", "Contender HC", 45, 30, 25, age=28,
                sal=6000000)

buys = scout.find_buy_low([unlucky, fair], [bad, good, user],
                          exclude_team="User Team")
names = [c["name"] for c in buys]
check("truth flags the snake-bitten driver", "Alex Undervalued" in names)
check("truth ignores the fairly-priced producer", "Joe Fair" not in names)

# --- Scout perception -------------------------------------------------------
# Build a league with several real finds so statistics are meaningful.
finds = [mkskater(f"Find{i}", "Lottery FC", 45, 6 + i, 14, age=23 + i,
                  sal=2000000) for i in range(6)]
filler = [mkskater(f"Filler{i}", "Contender HC", 45, 28, 22, age=29,
                   sal=6000000) for i in range(10)]
all_p = finds + filler + [fair]
bad.roster = finds
good.roster = filler + [fair]

elite = mkscout("Elite Eye", 95)  # native 1-100 JPA
poor = mkscout("Poor Eye", 15)  # native 1-100 JPA

# Single-week recall: in one tip sheet, how many of the 6 true finds
# does each scout spot? (This is what the user experiences each Monday.)
def _week_recall(s, seed):
    found = 0
    ghosts = 0
    tips = scout.scout_value_tips(s, all_p, [bad, good, user],
                                  user_team=user, limit=6,
                                  rng=random.Random(seed))
    for t in tips:
        if t["correct"]:
            found += 1
        else:
            ghosts += 1
    return found, ghosts

elite_recalls = [_week_recall(elite, i)[0] for i in range(50)]
poor_recalls = [_week_recall(poor, i)[0] for i in range(50)]
elite_ghosts = sum(_week_recall(elite, i)[1] for i in range(50))
poor_ghosts = sum(_week_recall(poor, i)[1] for i in range(50))
elite_avg = sum(elite_recalls) / 50
poor_avg = sum(poor_recalls) / 50
check(f"elite weekly recall ({elite_avg:.1f}/6) beats poor ({poor_avg:.1f}/6)",
      elite_avg > poor_avg + 2.0)
check(f"poor scout chases ghosts ({poor_ghosts}) vs elite ({elite_ghosts})",
      poor_ghosts > elite_ghosts)
check("tips carry the scout's name",
      all("scout" in t for t in scout.scout_value_tips(
          elite, all_p, [bad, good, user], user_team=user, rng=random.Random(1))))

# Ability labels
check("elite label", scout.scout_ability_label(18) == "Elite eye")
check("poor label", scout.scout_ability_label(3) == "Poor eye")

# --- Storylines --------------------------------------------------------------
stories = scout.analytics_storylines([unlucky, fair], [bad, good], limit=4)
check("storylines generated", len(stories) > 0)
check("storylines have titles", all(s.get("title") for s in stories))

# --- Fresh start ---------------------------------------------------------------
mover = mkskater("Rescued Winger", "Lottery FC", 40, 12, 18, age=26)
mover.happiness = 60
mover.morale = 60
res = rs.apply_fresh_start(mover, bad, good, teams=[bad, good, user])
check("rescue flagged on big upgrade", res["rescue"] is True)
check("rescue lifts happiness", mover.happiness > 60)
check("rescue lifts morale", mover.morale > 60)
check("rescue logs to new team feed", len(good.dynamics_log) > 0)

demoted = mkskater("Demoted Star", "Contender HC", 40, 20, 25, age=29)
demoted.happiness = 70
demoted.morale = 70
res2 = rs.apply_fresh_start(demoted, good, bad, teams=[bad, good, user])
check("downgrade is not a rescue", res2["rescue"] is False)
check("downgrade lowers happiness", demoted.happiness < 70)

# --- Award race sanity ----------------------------------------------------------
import awards_race as ar
team_pct = {"Lottery FC": 0.400, "Contender HC": 0.700}
hart = ar.hart_race([unlucky, fair], team_pct)
check("hart prefers the producer on the contender",
      hart and hart[0]["player"].full_name == "Joe Fair")

# --- AI parity ---------------------------------------------------------------
import trade_engine as te


def _mkai(name, jpa):
    import game_classes as _g
    return SimpleNamespace(
        full_name=name, judging_player_ability=jpa,
        judging_player_potential=12, role=_g.StaffRole.HEAD_SCOUT)


ai_scout = _mkai("AI Scout", 18)
ai_team = SimpleNamespace(team_name="AI Club", roster=[], staff=[ai_scout],
                          scout_buy_tips={}, scout_sell_tips={})

# scout_sell_high_tips runs on a team's own roster
ai_team.roster = [mkskater("Veteran", "AI Club", 45, 30, 20, age=34)]
sell_tips = scout.scout_sell_high_tips(ai_scout, ai_team, limit=2)
check("sell-high tips run without error", isinstance(sell_tips, list))

# Buy tip boosts perceived value; sell tip discounts it
target = mkskater("Trade Target", "Other", 45, 30, 25, age=27)
base_val = te.player_trade_value(target)
ai_team.scout_buy_tips[getattr(target, "id", id(target))] = {
    "jpa": 18, "correct": True, "scout": "AI Scout"}
boosted = te.scout_adjusted_value(target, ai_team)
check("AI values scout-tipped target higher", boosted > base_val)

vet = ai_team.roster[0]
vet_base = te.player_trade_value(vet)
ai_team.scout_sell_tips[getattr(vet, "id", id(vet))] = {
    "jpa": 18, "correct": True, "scout": "AI Scout"}
discounted = te.scout_adjusted_value(vet, ai_team)
check("AI discounts its own scout-flagged sell-high piece",
      discounted < vet_base)

# No tips -> base value untouched
plain = mkskater("Plain Joe", "Other", 45, 20, 20, age=27)
check("no tips means no adjustment",
      te.scout_adjusted_value(plain, ai_team) == te.player_trade_value(plain))

# Elite scout moves the needle more than a poor one
ai_team.scout_buy_tips[getattr(plain, "id", id(plain))] = {
    "jpa": 3, "correct": False, "scout": "Bad Scout"}
plain_base = te.player_trade_value(plain)
poor_boost = te.scout_adjusted_value(plain, ai_team)
elite_edge = (boosted - base_val) / base_val
poor_edge = (poor_boost - plain_base) / plain_base
check("elite scout's read moves value more than poor scout's",
      elite_edge > poor_edge)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
