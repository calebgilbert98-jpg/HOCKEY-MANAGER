#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""D11 measurement: before/after block%/miss%/on-net%/GPG per engine.

Paired-seed design: game i on each engine always uses the same seed, so
the BEFORE run and the AFTER run are directly comparable. Rosters are
generated fresh per game from a fixed seed.

Usage: python3 qa_d11_measure.py [n_games] [out_json]
Run BEFORE changes (baseline) and AFTER (same args) and diff.
"""
import sys, json, random, time
sys.path.insert(0, '/tmp/wt-retune-d11')
assert 'wt-retune-d11' in __import__('quick_sim').__file__
assert 'wt-retune-d11' in __import__('simulation').__file__

from quick_sim import AdvancedGameSim
from simulation import GameSim
from game_classes import League, PlayerPosition
from player_generator import PlayerGenerator

N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
OUT = sys.argv[2] if len(sys.argv) > 2 else None

def make_league(game_seed):
    rng = random.Random(4242 + game_seed)
    league = League("National Hockey League", "NHL")
    gen = PlayerGenerator()
    for team in league.teams[:2]:
        for _ in range(14):
            team.roster.append(gen.create_player(position=rng.choice(
                [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]),
                team_name=team.team_name))
        for _ in range(8):
            team.roster.append(gen.create_player(position=PlayerPosition.DEFENSE, team_name=team.team_name))
        for _ in range(3):
            team.roster.append(gen.create_player(position=PlayerPosition.GOALIE, team_name=team.team_name))
    return league

def gs_game(seed):
    random.seed(seed)
    league = make_league(seed)
    H, A = league.teams[0], league.teams[1]
    sim = GameSim(H, A)
    winner, loser, scores, log, notable = sim.run()
    att = blk = onn = 0
    for tn, st in sim.team_stats.items():
        att += st.get('shot_attempts', 0)
        blk += st.get('blocked_shots', 0)
        onn += st.get('shots_on_goal', 0)
    goals = scores[0] + scores[1]
    miss = att - blk - onn
    return dict(att=att, blk=blk, miss=miss, onn=onn, goals=goals)

def qs_game(seed):
    random.seed(seed)
    league = make_league(seed)
    H, A = league.teams[0], league.teams[1]
    q = AdvancedGameSim(H, A)
    out = q.run()
    scores = out[2]
    evs = q.events
    blocked = sum(1 for e in evs if e.get('event') == 'Shot Blocked')
    shots = sum(1 for e in evs if e.get('event') == 'Shot')
    goals = scores[0] + scores[1]
    saves = 0
    for tn, pd in q.stats.items():
        for pid, st in pd.items():
            saves += st.get('saves', 0)
    miss = shots - saves
    onn = saves + goals
    att = blocked + shots
    return dict(att=att, blk=blocked, miss=miss, onn=onn, goals=goals)

def summarize(rows):
    n = len(rows)
    A = sum(r['att'] for r in rows); B = sum(r['blk'] for r in rows)
    M = sum(r['miss'] for r in rows); O = sum(r['onn'] for r in rows)
    G = sum(r['goals'] for r in rows)
    return dict(games=n, attempts=A,
                block_pct=round(100.0*B/A, 2), miss_pct=round(100.0*M/A, 2),
                onnet_pct=round(100.0*O/A, 2),
                gpg=round(G/n, 3), att_per_game=round(A/n, 1))

t0 = time.time()
gs_rows, qs_rows = [], []
for i in range(N):
    gs_rows.append(gs_game(7000+i))
    qs_rows.append(qs_game(9000+i))
    if (i+1) % 25 == 0:
        print(f"  ... {i+1}/{N} games per engine", flush=True)
res = dict(gamesim=summarize(gs_rows), advgs=summarize(qs_rows),
           elapsed_s=round(time.time()-t0, 1))
print(json.dumps(res, indent=1))
if OUT:
    with open(OUT, 'w') as f:
        json.dump(res, f, indent=1)
    print(f"wrote {OUT}", flush=True)
