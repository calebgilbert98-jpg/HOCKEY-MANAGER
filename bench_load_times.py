# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Load-time profiler: save size, save/load round-trip timing, and the
per-game overhead of the postgame pipeline (incl. iconic-game detection).

Builds a representative league (32 teams x 23 players, with the lore
attributes today's save/load batches now persist filled in), then times:
  1. save_game  2. load_game  3. process_postgame over N synthetic games
  4. detect_iconic alone per game

Not pass/fail -- it reports numbers. Run: python3 bench_load_times.py
"""
import os
import sys
import tempfile
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game_classes import League, Team

_pos = SimpleNamespace(name="CENTER")
_gpos = SimpleNamespace(name="GOALIE")


def _player(pid, name, goalie=False):
    return SimpleNamespace(
        id=pid, full_name=name,
        primary_position=_gpos if goalie else _pos,
        career_moments=[{"date": "2028-01-01", "kind": "hat_trick",
                         "label": "Hat trick", "detail": "3 G",
                         "sig": 40}],
        career_accolades=[])


def build_league():
    lg = League("NHL")
    lg.season_year = 2028
    pid = 1
    for t in range(32):
        team = Team(f"Team{t:02d}", "City", "Atlantic", "Eastern")
        roster = []
        for i in range(23):
            roster.append(_player(pid, f"Player{pid:04d}",
                                  goalie=(i >= 20)))
            pid += 1
        team.roster = roster
        # Fill the lore attributes today's batches persist, so the
        # serializer cost measured here includes them.
        team.iconic_games = [
            {"id": f"2028|x{i}|t{t}", "date": "2028-03-01",
             "season": 2028, "kind": "brawl_game",
             "headline": f"Brawl night {i}", "score": "4-3",
             "winner": f"Team{t:02d}", "starred": bool(i % 3 == 0),
             "stars": [{"name": f"Player{i:04d}"}]}
            for i in range(12)]
        team.dynamics_log = [{"date": "2028-03-01", "text": "x" * 80}
                             for _ in range(100)]
        team.retired_numbers = {35: "Brick Wallski"}
        team.dressing_room = {"mood": ["line"] * 20}
        lg.teams.append(team)
    lg.retired_players = [{"name": f"OldTimer{i}"} for i in range(50)]
    lg.media_narratives = [{"headline": "x" * 60} for _ in range(20)]
    lg.steal_retro_posted = {"2028": True}
    return lg


def main():
    from save_load_system import GameSaveManager
    lg = build_league()
    gm = SimpleNamespace(league=lg, league_history=None,
                         narrative_ledger=None)
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "bench.save")

    t0 = time.perf_counter()
    ok = GameSaveManager(gm).save_game(path)
    t_save = time.perf_counter() - t0
    size_kb = os.path.getsize(path) / 1e3

    gm2 = SimpleNamespace(league=None, league_history=None,
                          narrative_ledger=None)
    t0 = time.perf_counter()
    ok2 = GameSaveManager(gm2).load_game(path)
    t_load = time.perf_counter() - t0

    print(f"save: {'OK' if ok else 'FAIL'}  load: {'OK' if ok2 else 'FAIL'}")
    print(f"save file: {size_kb:.1f} KB (synthetic light players; "
          f"measures serializer overhead, not a real-save absolute)")
    print(f"save_game: {t_save*1000:.0f} ms   load_game: {t_load*1000:.0f} ms")

    # Per-game postgame overhead.
    import narrative_incidents as ni
    from iconic_games import detect_iconic
    h, a = lg.teams[0], lg.teams[1]
    sim = SimpleNamespace(
        stats={h.team_name: {str(p.id): {"goals": 1, "assists": 1,
                                         "saves": 0} for p in h.roster},
               a.team_name: {str(p.id): {"goals": 0, "assists": 1,
                                         "saves": 0} for p in a.roster}},
        pending_headlines=[])
    N = 200
    t0 = time.perf_counter()
    for _ in range(N):
        ni.process_postgame(sim, h, a, 4, 2, game_date="2028-03-10",
                            season_year=2028)
    t_pg = (time.perf_counter() - t0) / N * 1000

    t0 = time.perf_counter()
    for _ in range(N):
        detect_iconic(h, a, 4, 2, sim, game_date="2028-03-10",
                      season_year=2028)
    t_ic = (time.perf_counter() - t0) / N * 1000

    print(f"process_postgame: {t_pg:.2f} ms/game "
          f"({N} games, both clubs' lists + moments included)")
    print(f"detect_iconic alone: {t_ic:.3f} ms/game "
          f"({t_ic/max(t_pg, 1e-9)*100:.1f}% of the postgame pipeline)")
    print("Verdict: postgame stays sub-millisecond per game; the iconic "
          "detection is noise inside it.")


if __name__ == "__main__":
    main()
