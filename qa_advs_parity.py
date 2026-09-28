"""QA: AdvancedGameSim parity -- goalie pull/6-on-5, last-change matching,
shift-fatigue. Headless. Run: python3 qa_advs_parity.py"""
import sys, random
sys.path.insert(0, '.')
from quick_sim import AdvancedGameSim
from game_classes import League, PlayerPosition
from player_generator import PlayerGenerator
from shift_engine import fatigue_curve

PASS, FAIL = 0, 0
def check(name, cond):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  ok   {name}")
    else: FAIL += 1; print(f"  FAIL {name}")

def make_league(n_rosters=4):
    random.seed(1234)
    league = League("National Hockey League", "NHL")
    gen = PlayerGenerator()
    for team in league.teams[:n_rosters]:
        for _ in range(14):
            team.roster.append(gen.create_player(position=random.choice(
                [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]),
                team_name=team.team_name))
        for _ in range(8):
            team.roster.append(gen.create_player(position=PlayerPosition.DEFENSE, team_name=team.team_name))
        for _ in range(3):
            team.roster.append(gen.create_player(position=PlayerPosition.GOALIE, team_name=team.team_name))
    return league

league = make_league()
H, A = league.teams[0], league.teams[1]
HN, AN = H.team_name, A.team_name

# --- fatigue curve ---
check("curve 1.0 at/under 40s", fatigue_curve(0) == 1.0 and fatigue_curve(40) == 1.0)
check("curve decays past 40s", fatigue_curve(50) == 0.98 and fatigue_curve(60) == 0.96)
check("curve floors at 0.90", fatigue_curve(500) == 0.90)

# --- pull eligibility guards ---
sim = AdvancedGameSim(H, A)
check("no pull in period 1", not sim._pull_eligible(H, HN))
sim.period = 3; sim.time = 3500.0
sim.score[HN] = 2; sim.score[AN] = 2
check("no pull when tied", not sim._pull_eligible(H, HN))
sim.score[HN] = 3; sim.score[AN] = 2
check("no pull when leading", not sim._pull_eligible(H, HN))
sim.score[HN] = 1; sim.score[AN] = 4
check("no pull down 3", not sim._pull_eligible(H, HN))
sim.score[HN] = 2; sim.score[AN] = 3
check("eligible down 1, late", sim._pull_eligible(H, HN))
sim.time = 2500.0  # ~18 min left
check("not eligible down 1, early in 3rd", not sim._pull_eligible(H, HN))
sim.time = 3550.0
sim.pk_team = HN
check("no pull shorthanded", not sim._pull_eligible(H, HN))
sim.pk_team = None
sim.period = 4
check("no pull in OT", not sim._pull_eligible(H, HN))
sim.period = 3

# --- full games: pulls happen, ENGs marked, nobody stuck pulled ---
pulls = engs = 0
for i in range(10):
    s = AdvancedGameSim(H, A)
    s.run()
    pulls += sum(1 for e in s.events if e.get('event') == 'GoaliePulled')
    for e in s.event_log:
        if e.get('type') == 'GOAL_ADVANCED' and e.get('details', {}).get('goal_type') == 'empty_net':
            engs += 1
            check("ENG charges no goalie", e['details'].get('goaltender_id') is None)
    check(f"game {i}: no stuck pull", not s.goalie_pulled)
check("pulls occur over 10 games", pulls > 0)
print(f"  info pulls={pulls} ENGs={engs} over 10 games")

# --- last change: away 1st line -> home answers 3rd F + 1st D ---
s = AdvancedGameSim(H, A)
for p in H.roster:  # zero fatigue so the matchup pick is taken
    s.stats[HN].setdefault(p.id, {})['fatigue'] = 0
fw, df, g, fi, di, directed = s._select_home_lines(HN, 0)
check("vs 1st: home sends 3rd line", fi == 2 and directed)
check("vs 1st: home sends 1st pair", di == 0)
fw, df, g, fi, di, directed = s._select_home_lines(HN, 3)
check("vs 4th: home exploits with 1st", fi == 0 and directed)
fw, df, g, fi, di, directed = s._select_home_lines(HN, 1)
check("vs 2nd: home rolls", not directed)
# user prefs honored
H.line_matchups = {"F": [None, None, 3, None], "D": [None, None, None]}
fw, df, g, fi, di, directed = s._select_home_lines(HN, 2)
check("pref: F3 vs opp 3rd", fi == 2 and directed)
del H.line_matchups
# fatigue veto: gas the 3rd line, home should roll fresh instead
for p in s.lineups[HN]['Forwards'][2]:
    s.stats[HN][p.id]['fatigue'] = 50
fw, df, g, fi, di, directed = s._select_home_lines(HN, 0)
check("fatigue veto rolls fresh legs", fi != 2)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
