"""QA: BUG-021 -- UFA lowball exploit closed.

The old money curve ((ratio-0.65)/0.65) left full-market offers at
money_score 0.54 and let 50%-of-market offers ride on the non-money parts:
UFAs accepted half-price ~1 in 3. Now: full market -> money_score 1.0, and
an insult-offer guard (<65% of market, cup-chaser discount exempted)
cliffs appeal. Checks the curve shape, the guard, and the exemption.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DISPLAY", ":99")

passed = failed = 0
def check(name, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"PASS: {name}")
    else: failed += 1; print(f"FAIL: {name} {detail}")

from main import GameManager
from game_classes import League
import player_decision as pd

gm = GameManager()
gm.league = League(league_name="National Hockey League")
league = gm.league

class FakeTeam:
    team_name = "Chicago Blackhawks"
team = FakeTeam()

# build a UFA: 84 ovr-ish, money ambition, no current team
from game_classes import Player, Contract, PlayerPosition
def _mk(name, age, ovr, ambition, salary=7_000_000):
    fn, ln = name.split(" ", 1)
    pl = Player(first_name=fn, last_name=ln, age=age,
                primary_position=PlayerPosition.LEFT_WING)
    pl.overall_rating = lambda: float(ovr)
    pl.contract = Contract(salary=salary, years_remaining=0)
    pl.ambition = ambition
    pl.loyalty = 50
    pl.happiness = 70
    try:
        pd.ensure_decision_fields(pl)
    except Exception:
        pass
    return pl

p = _mk("Test Winger", 27, 84, "money")

mv = pd._market_value(p)
check("market value sane", mv > 3_000_000, f"mv={mv}")

def prob(frac):
    pr, _ = pd.ufa_accept_probability(p, team, int(mv * frac), 4, league=league)
    return pr

p100, p80, p70, p60, p50 = prob(1.0), prob(0.8), prob(0.7), prob(0.6), prob(0.5)
check("full market beats 80%", p100 > p80, f"{p100:.2f} vs {p80:.2f}")
check("monotone-ish decline to 70%", p80 >= p70 >= p60, f"{p80:.2f} {p70:.2f} {p60:.2f}")
check("insult guard: 50% far below 70%", p50 < p70 - 0.15, f"50%={p50:.2f} 70%={p70:.2f}")
check("insult guard: 60% far below 70%", p60 < p70 - 0.10, f"60%={p60:.2f} 70%={p70:.2f}")
check("50% offer is a real longshot", p50 < 0.30, f"p50={p50:.2f}")
check("70% still negotiable (no cliff too early)", p70 > 0.25, f"p70={p70:.2f}")

# insult reason surfaces
_, reasons = pd.ufa_accept_probability(p, team, int(mv * 0.5), 4, league=league)
check("insult reason shown", any("insult" in r for r in reasons), str(reasons))

# cup-chaser exemption: 35yo cup ambition at 60% keeps real appeal
p2 = _mk("Old Chaser", 35, 82, "cup", salary=5_000_000)
mv2 = pd._market_value(p2)
p60c, r60c = pd.ufa_accept_probability(p2, team, int(mv2 * 0.6), 3, league=league)
check("cup-chaser discount exempt from insult guard", p60c > 0.30, f"p={p60c:.2f}")
check("discount reason shown", any("Cup" in r for r in r60c), str(r60c))

# non-exempt 35yo at 60% still insulted
p3 = _mk("Old Mercenary", 35, 82, "money", salary=5_000_000)
mv3 = pd._market_value(p3)
p60m, _ = pd.ufa_accept_probability(p3, team, int(mv3 * 0.6), 3, league=league)
check("old mercenary not exempt", p60m < 0.30, f"p={p60m:.2f}")

print(f"\n{'='*40}\nQA bug021_ufa_lowball: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
