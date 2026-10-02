# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: stat recording -- hits, blocks, faceoffs, takeaways, giveaways.

Verifies on BOTH sim paths (GameSim and AdvancedGameSim) that per-game
stats are recorded (not zeros) and that team records update for the
dashboard. Headless. Run: python3 qa_stat_recording.py
"""
import sys, random
sys.path.insert(0, '.')
random.seed(20261002)

from quick_sim import AdvancedGameSim
from simulation import GameSim
from game_classes import (
    League, Team, PlayerPosition,
    roll_defensive_game_stats, roll_faceoff_game_stats,
)
from player_generator import PlayerGenerator

PASS, FAIL = 0, 0
def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")


def make_league():
    league = League("National Hockey League", "NHL")
    gen = PlayerGenerator()
    for team in league.teams[:2]:
        fwds, dmen, goalies = [], [], []
        for _ in range(12):
            fwds.append(gen.create_player(
                position=random.choice([PlayerPosition.CENTER,
                                        PlayerPosition.LEFT_WING,
                                        PlayerPosition.RIGHT_WING]),
                team_name=team.team_name))
        for _ in range(6):
            dmen.append(gen.create_player(
                position=PlayerPosition.DEFENSE, team_name=team.team_name))
        for _ in range(2):
            goalies.append(gen.create_player(
                position=PlayerPosition.GOALIE, team_name=team.team_name))
        team.roster = fwds + dmen + goalies
    return league


league = make_league()
H, A = league.teams[0], league.teams[1]
HN, AN = H.team_name, A.team_name

# ---------------------------------------------------------------- unit: shared rolls
print("== shared roll functions ==")
_h, _t, _b = roll_defensive_game_stats(H.roster[0])
check("roll_defensive_game_stats returns ints", all(isinstance(v, int) for v in (_h, _t, _b)))
check("roll_defensive_game_stats never raises", isinstance(roll_defensive_game_stats(None), tuple))

_fh, _fa = roll_faceoff_game_stats(H.roster, A.roster)
_tot_fo = sum(w + l for w, l in list(_fh.values()) + list(_fa.values()))
check("roll_faceoff_game_stats returns two dicts", isinstance(_fh, dict) and isinstance(_fa, dict))
check(f"faceoff total sane (~124 entries for ~62 draws, got {_tot_fo})", 80 <= _tot_fo <= 170)
check("faceoff never raises on junk", roll_faceoff_game_stats(None, None) == ({}, {}))
check("someone won a faceoff", sum(w for w, l in list(_fh.values()) + list(_fa.values())) > 0)

# ---------------------------------------------------------------- GameSim path
print("== GameSim path (per-game game_stats) ==")
gsim = GameSim(H, A)
try:
    _w, _l, _s, _gl, _nt = gsim.run()
except TypeError:
    # run() signature may differ; try bare
    _w, _l, _s, _gl, _nt = gsim.run(), None, None, None, None
_gst = getattr(gsim, 'game_stats', {}) or {}
_g_hits = sum(g.get('hits', 0) for g in _gst.values())
_g_blk = sum(g.get('blocked_shots', 0) for g in _gst.values())
_g_fo = sum(g.get('faceoffs_won', 0) for g in _gst.values())
_g_tk = sum(g.get('takeaways', 0) for g in _gst.values())
_g_gv = sum(g.get('giveaways', 0) for g in _gst.values())
check(f"GameSim hits > 0 (got {_g_hits})", _g_hits > 0)
check(f"GameSim blocks > 0 (got {_g_blk})", _g_blk > 0)
check(f"GameSim faceoffs > 0 (got {_g_fo})", _g_fo > 0)
check(f"GameSim takeaways > 0 (got {_g_tk})", _g_tk > 0)
# Giveaways are rarer; informational only (not in the required stat set).
print(f"  info GameSim giveaways: {_g_gv} (informational)")

# ---------------------------------------------------------------- AdvGS path via _process_single_game_result
print("== AdvGS path (via _process_single_game_result) ==")
import main as _main_mod

# Fresh league: GameSim mutates player state, so don't reuse those teams.
league2 = make_league()
H2, A2 = league2.teams[0], league2.teams[1]
HN2, AN2 = H2.team_name, A2.team_name

sim = AdvancedGameSim(H2, A2)
winner, loser, scores, events, notable_events = sim.run()

# Minimal harness: uninitialized HockeyManagerGUI with stubbed collaborators.
mgr = _main_mod.HockeyManagerGUI.__new__(_main_mod.HockeyManagerGUI)
mgr.league = league2
league2.standings = {}
mgr._grudge_week_grade = lambda *a, **k: None
mgr._grudge_week_market = lambda *a, **k: None
mgr._calculate_player_ratings = lambda *a, **k: {}
mgr._record_game_result = lambda gr: setattr(mgr, '_last_gr', gr)
mgr._snapshot_game_toi_fatigue = lambda *a, **k: ({}, {})
mgr.media_system = None
mgr.game_results = []
mgr.user_team = None  # avoid tkinter __getattr__ recursion

from datetime import date
mgr._process_single_game_result(
    date(2026, 9, 26), H2, A2, winner, loser, scores, events,
    notable_events, sim, stats_from_events=True, preseason=False)

gr = mgr._last_gr
_pgs = gr['game_stats'] or {}
_q_hits = sum(g.get('hits', 0) for g in _pgs.values())
_q_blk = sum(g.get('blocked_shots', 0) for g in _pgs.values())
_q_fo = sum(g.get('faceoffs_won', 0) for g in _pgs.values())
_q_tk = sum(g.get('takeaways', 0) for g in _pgs.values())
check(f"AdvGS per-game hits > 0 (got {_q_hits})", _q_hits > 0)
check(f"AdvGS per-game blocks > 0 (got {_q_blk})", _q_blk > 0)
check(f"AdvGS per-game faceoffs > 0 (got {_q_fo})", _q_fo > 0)
check(f"AdvGS per-game takeaways > 0 (got {_q_tk})", _q_tk > 0)

# Team stats section of the box score
_ts = gr.get('team_stats') or {}
_th = sum(t.get('hits', 0) for t in _ts.values())
_tb = sum(t.get('blocked_shots', 0) for t in _ts.values())
_tf = sum(t.get('faceoffs_won', 0) for t in _ts.values())
check(f"AdvGS team hits > 0 (got {_th})", _th > 0)
check(f"AdvGS team blocks > 0 (got {_tb})", _tb > 0)
check(f"AdvGS team faceoffs > 0 (got {_tf})", _tf > 0)

# Season totals agree with per-game (single roll)
_s_hits = sum(getattr(p.stats, 'hits', 0) for p in H2.roster + A2.roster)
check(f"season hits ({_s_hits}) == per-game hits ({_q_hits})", _s_hits == _q_hits)

# No internal bookkeeping leaked into stored game_stats
check("no _def_roll leaked", all('_def_roll' not in g for g in _pgs.values()))

# ---------------------------------------------------------------- team record sync (dashboard)
print("== team record sync ==")
check(f"winner team object wins=1 (got {winner.wins})", winner.wins == 1)
check(f"loser team object losses=1 (got {loser.losses})", loser.losses == 1)
check(f"games_played=1 both (got {H2.games_played},{A2.games_played})",
      H2.games_played == 1 and A2.games_played == 1)
check("goals_for tracked", H2.goals_for == scores[0] and A2.goals_for == scores[1])
check("standings still updated",
      league2.standings[HN2]['W'] + league2.standings[AN2]['W'] == 1)
# Dashboard reads team.wins/losses -- would show 1-0-0 not 0-0-0
check("dashboard record non-zero", (winner.wins, winner.losses) != (0, 0))

# ---------------------------------------------------------------- batch path
print("== batch path (_update_standings_fast) ==")
_w0, _gp0 = H2.wins, H2.games_played
_al0 = A2.losses
mgr._update_standings_fast(H2, A2, H2, (3, 2), went_to_ot=False, preseason=False)
check("batch: winner wins+1", H2.wins == _w0 + 1)
check("batch: loser losses+1", A2.losses == _al0 + 1)
check("batch: games_played+1", H2.games_played == _gp0 + 1)
check("batch: goals_for", H2.goals_for >= 3 and A2.goals_for >= 2)

# Preseason guard: nothing touches records
_pw, _pl = H2.wins, A2.losses
mgr._update_standings_fast(H2, A2, H2, (5, 0), went_to_ot=False, preseason=True)
check("preseason: no record change", H2.wins == _pw and A2.losses == _pl)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
