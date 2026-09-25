#!/usr/bin/env python3
"""Analyze Puck Dynasty beta telemetry against NHL benchmarks.

Reads telemetry/games.jsonl (one JSON record per simulated game, written
automatically by GameSim) and reports league averages vs NHL targets.

Usage:
    python3 analyze_telemetry.py              # all games
    python3 analyze_telemetry.py --last 50    # most recent 50 games
    python3 analyze_telemetry.py --sim abc123 # only one sim build
    python3 analyze_telemetry.py --by-sim     # split report per sim build
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telemetry import NHL_BENCHMARKS, get_log_path


def load_games(path, last=None, sim=None):
    games = []
    if not os.path.exists(path):
        return games
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                g = json.loads(line)
            except json.JSONDecodeError:
                continue
            if sim and not g.get("sim", "").startswith(sim):
                continue
            games.append(g)
    if last:
        games = games[-last:]
    return games


def game_metrics(g):
    t = g["teams"]
    names = list(t.keys())
    goals = g["home_score"] + g["away_score"]
    shots = sum(t[n]["shots"] for n in names)
    saves = sum(t[n]["goalie"]["shots_against"] for n in names)
    stopped = sum(t[n]["goalie"]["saves"] for n in names)
    pp_opps = sum(t[n]["pp_opps"] for n in names)
    pp_goals = sum(t[n]["pp_goals"] for n in names)
    home_name = g.get("home", names[0])
    return {
        "goals": goals,
        "shots": shots,
        "shooting_pct": 100.0 * goals / shots if shots else 0,
        "save_pct": stopped / saves if saves else 0,
        "penalties": g.get("penalties", 0),
        "pim": sum(t[n]["pim"] for n in names),
        "pp_opps": pp_opps,
        "pp_pct": 100.0 * pp_goals / pp_opps if pp_opps else 0,
        "icings": g.get("icings", 0),
        "offsides": g.get("offsides", 0),
        "hits": sum(t[n]["hits"] for n in names),
        "fights": g.get("fights", 0),
        "penalty_shots": g.get("penalty_shots", 0),
        "faceoff_pct": t.get(home_name, {}).get("faceoff_pct", 50.0),
    }


def flag(value, lo, hi):
    if lo <= value <= hi:
        return "OK"
    # within 30% of the band edge -> watch, else off
    span = hi - lo or 1.0
    if (lo - 0.3 * span) <= value <= (hi + 0.3 * span):
        return "WATCH"
    return "OFF"


def report(games, title):
    print(f"\n=== {title} ({len(games)} games) ===")
    if not games:
        print("no games logged yet -- play or simulate some games first.")
        return
    metrics = [game_metrics(g) for g in games]
    sims = sorted({g.get("sim", "?") for g in games})
    print(f"sim builds: {', '.join(sims)}")
    print(f"{'metric':<22}{'avg':>8}  {'NHL target':<16}{'flag':<7} hint")
    print("-" * 90)
    offs = []
    for key, (lo, hi, label, hint) in NHL_BENCHMARKS.items():
        vals = [m[key] for m in metrics]
        avg = sum(vals) / len(vals)
        st = flag(avg, lo, hi)
        target = f"{lo}-{hi}"
        mark = {"OK": "[ok]", "WATCH": "[~]", "OFF": "[!]"}[st]
        print(f"{label:<22}{avg:>8.2f}  {target:<16}{mark:<7} {hint if st == 'OFF' else ''}")
        if st == "OFF":
            offs.append((label, avg, lo, hi, hint))
    if offs:
        print("\nNeeds tuning:")
        for label, avg, lo, hi, hint in offs:
            print(f"  - {label}: {avg:.2f} vs NHL {lo}-{hi} -- {hint}")
    else:
        print("\nAll metrics within NHL range. Nice.")


def main():
    ap = argparse.ArgumentParser(description="Analyze Puck Dynasty telemetry")
    ap.add_argument("--last", type=int, default=None)
    ap.add_argument("--sim", default=None)
    ap.add_argument("--by-sim", action="store_true")
    args = ap.parse_args()

    path = get_log_path()
    if args.by_sim:
        games = load_games(path)
        by_sim = {}
        for g in games:
            by_sim.setdefault(g.get("sim", "?"), []).append(g)
        for sim_id in sorted(by_sim):
            report(by_sim[sim_id][-args.last:] if args.last else by_sim[sim_id],
                   f"sim {sim_id}")
    else:
        games = load_games(path, last=args.last, sim=args.sim)
        title = "telemetry report"
        if args.sim:
            title += f" (sim {args.sim})"
        if args.last:
            title += f" (last {args.last})"
        report(games, title)
        print(f"\nlog: {path}")


if __name__ == "__main__":
    main()
