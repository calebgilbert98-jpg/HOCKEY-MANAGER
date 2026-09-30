"""Full-season scoring validation for Part A + Part B.

Runs 1,312 AdvancedGameSim games (82 per team) and reports Muck's metrics:
  - League GPG (target 2.70-3.60)
  - Assists/goal (target 1.55-1.70)
  - Art Ross total, top-3 goal share, best-team win%, elite playmaker assists

Usage: python3 validate_scoring_season.py [seed]
"""
import sys, os, random
sys.path.insert(0, '/home/hatch/workspace/playthrough')
sys.path.insert(0, '/home/hatch/workspace/HOCKEY-MANAGER')
from pt import patch_dialogs_headless, SAVES
patch_dialogs_headless()
from main import GameManager
from save_load_system import GameSaveManager

def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    random.seed(seed)
    
    gm = GameManager()
    mgr = GameSaveManager(gm)
    assert mgr.load_game(os.path.join(SAVES, "s2_deadline.hm"))
    lg = gm.league
    
    from quick_sim import AdvancedGameSim
    
    team_games = {t.team_name: 0 for t in lg.teams}
    team_wins = {t.team_name: 0 for t in lg.teams}
    team_goals = {t.team_name: 0 for t in lg.teams}
    player_pts = {}
    
    total_goals = 0
    total_assists = 0
    games_played = 0
    
    teams = [t for t in lg.teams
             if getattr(t, 'league_name', '') == 'National Hockey League']
    print(f"Using {len(teams)} NHL teams", flush=True)
    # Pre-generate 1312 balanced matchups: each team plays 82 games
    # Simple round-robin style: shuffle team list, pair up, repeat
    matchups = []
    games_needed = {t.team_name: 82 for t in teams}
    
    # Create a list of team slots (82 copies of each team), shuffle, pair
    slots = []
    for t in teams:
        slots.extend([t] * 82)
    random.shuffle(slots)
    # Pair consecutive slots (avoid self-matchups by reshuffling if needed)
    for i in range(0, len(slots) - 1, 2):
        h, a = slots[i], slots[i+1]
        if h is a:
            # Swap with next pair
            if i + 3 < len(slots):
                slots[i+1], slots[i+3] = slots[i+3], slots[i+1]
                h, a = slots[i], slots[i+1]
            else:
                continue
        matchups.append((h, a))
    
    print(f"Generated {len(matchups)} matchups", flush=True)
    
    for h, a in matchups:
        sim = AdvancedGameSim(h, a)
        sim.run()
        games_played += 1
        
        hs = sim.score.get(h.team_name, 0)
        aws = sim.score.get(a.team_name, 0)
        team_games[h.team_name] += 1
        team_games[a.team_name] += 1
        team_goals[h.team_name] += hs
        team_goals[a.team_name] += aws
        total_goals += hs + aws
        
        if hs > aws:
            team_wins[h.team_name] += 1
        elif aws > hs:
            team_wins[a.team_name] += 1
        
        for e in sim.events:
            if e.get('event') == 'Goal':
                total_assists += len(e.get('assists', []))
        
        for tn, tm in [(h.team_name, h), (a.team_name, a)]:
            for pid, st in sim.stats[tn].items():
                if pid not in player_pts:
                    pname = "?"
                    for p in tm.roster:
                        if p.id == pid:
                            pname = getattr(p, 'full_name', getattr(p, 'last_name', '?'))
                            break
                    player_pts[pid] = [pname, tn, 0, 0]
                player_pts[pid][2] += st.get('goals', 0)
                player_pts[pid][3] += st.get('assists', 0)
        
        if games_played % 300 == 0:
            print(f"  ... {games_played} games", flush=True)
    
    print(f"\n=== SCORING VALIDATION (seed {seed}) ===", flush=True)
    print(f"Games: {games_played}", flush=True)
    
    gpg = total_goals / (games_played * 2)
    print(f"League GPG/team: {gpg:.2f} (target 2.70-3.60)", flush=True)
    
    ag = total_assists / total_goals if total_goals else 0
    print(f"Assists/goal: {ag:.2f} (target 1.55-1.70)", flush=True)
    
    leaders = sorted(player_pts.values(), key=lambda x: x[2] + x[3], reverse=True)[:5]
    print(f"\nTop 5 scorers:", flush=True)
    for name, team, g, a in leaders:
        print(f"  {name} ({team}): {g}G + {a}A = {g+a}P", flush=True)
    
    shares = []
    for t in teams:
        tn = t.team_name
        tgoals = team_goals[tn]
        if tgoals == 0:
            continue
        team_players = [v for v in player_pts.values() if v[1] == tn]
        team_players.sort(key=lambda x: x[2], reverse=True)
        top3 = sum(p[2] for p in team_players[:3])
        shares.append(top3 / tgoals)
    avg_share = sum(shares) / len(shares) if shares else 0
    print(f"\nTop-3 goal share (avg): {avg_share:.1%} (target 35-40%)", flush=True)
    
    best = max(team_wins.items(), key=lambda x: x[1] / max(1, team_games[x[0]]))
    best_pct = best[1] / team_games[best[0]]
    print(f"Best team: {best[0]} {best[1]}-{team_games[best[0]]-best[1]} ({best_pct:.1%}) (target <=65%)", flush=True)
    
    ast_leaders = sorted(player_pts.values(), key=lambda x: x[3], reverse=True)[:3]
    print(f"\nTop 3 assist men:", flush=True)
    for name, team, g, a in ast_leaders:
        print(f"  {name} ({team}): {a}A", flush=True)

if __name__ == "__main__":
    main()
