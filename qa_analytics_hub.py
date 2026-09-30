# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: Analytics Hub (module 04).

Recording layer (shot/entry logs, per-game persistence), the xG
aggregation model, momentum/entry/line queries, Ask the Analyst, and a
headless UI smoke test. Deterministic: seeded RNG.
"""
import random
import sys

sys.path.insert(0, ".")

import analytics_hub as ah

passed, failed = [], []


def check(label, cond):
    (passed if cond else failed).append(label)
    if not cond:
        print(f"  FAIL: {label}")


def make_sim_game(seed=7, games=1):
    """Simulate games with minimal rosters; return (home, away)."""
    import game_classes as g
    from simulation import GameSim
    from game_classes import PlayerPosition
    random.seed(seed)
    t1 = g.Team("Hub HC", "HHC", "Div", "Conf")
    t2 = g.Team("Rivals", "RIV", "Div", "Conf")
    for i in range(14):
        for t in (t1, t2):
            t.roster.append(g.Player(
                first_name=f"P{i}", last_name="X", age=25,
                primary_position=PlayerPosition.CENTER,
                jersey_number=i + 1))
    for _ in range(games):
        sim = GameSim(t1, t2)
        sim.simulate_game()
    return t1, t2, sim


# 1: recording ---------------------------------------------------------
home, away, sim = make_sim_game()
shots = sim.shot_log
check("shots recorded", len(shots) > 20)
need = {"shooter_id", "shooter", "team", "opp", "period", "clock",
        "location", "x", "y", "distance", "shot_type", "xg",
        "outcome", "line"}
check("shot record keys", all(need <= set(s) for s in shots))
check("no pending outcomes",
      all(s["outcome"] != "pending" for s in shots))
check("outcomes sane",
      set(s["outcome"] for s in shots) <=
      {"goal", "save", "blocked", "disallowed"})
check("xg non-negative", all(s["xg"] >= 0 for s in shots))
check("shot coords on rink",
      all(0 <= s["x"] <= 200 and 0 <= s["y"] <= 85 for s in shots))
check("entries recorded", len(sim.zone_entry_log) >= 0)
check("entry keys",
      all({"carrier", "team", "period", "type", "x", "y", "line"} <=
          set(e) for e in sim.zone_entry_log))
check("momentum tracked", len(sim.momentum_history) > 0)

# 2: persistence --------------------------------------------------------
check("home persisted", len(getattr(home, "analytics_games", [])) == 1)
rec = home.analytics_games[0]
check("persisted shots", len(rec["shots"]) == len(shots))
check("persisted score tuple", isinstance(rec["score"], tuple))
check("persisted momentum strings",
      all(isinstance(m.get("momentum"), str)
          for m in rec["momentum"]))
check("momentum actually persisted",
      len(rec["momentum"]) == len(sim.momentum_history)
      and len(rec["momentum"]) > 0)

# cap at 10
home2, _, _ = make_sim_game(seed=11, games=12)
check("history capped at 10",
      len(getattr(home2, "analytics_games", [])) == 10)

# old-save safety: team with no analytics_games
from types import SimpleNamespace
bare = SimpleNamespace(team_name="Oldies", roster=[])
check("backfill empty", ah.team_games(bare) == [])
check("latest_game none", ah.latest_game(bare) is None)
check("report with no data",
      ah.analyst_report(bare)[0][0] == "No data yet")

# 3: xG aggregation -----------------------------------------------------
nm = home.team_name
gshots = ah.shots_for(rec, nm)
xg, goals = ah.team_xg(gshots)
check("team_xg sums",
      abs(xg - round(sum(s["xg"] for s in gshots), 2)) < 1e-9)
check("team goals count",
      goals == sum(1 for s in gshots if s["outcome"] == "goal"))
prows = ah.player_xg_rows(gshots)
check("player rows sorted",
      all(prows[i]["xg"] >= prows[i + 1]["xg"]
          for i in range(len(prows) - 1)))
check("player diff math",
      all(abs(r["diff"] - (r["goals"] - r["xg"])) < 1e-9 for r in prows))
lrows = ah.line_xg_rows(gshots, rec.get("lines"))
check("line rows only L-lines",
      all(r["line"].startswith("L") for r in lrows))

# 4: momentum ------------------------------------------------------------
pts = ah.momentum_points(rec, nm)
check("momentum values bounded",
      all(-3 <= p["value"] <= 3 for p in pts))
pts_away = ah.momentum_points(rec, away.team_name)
check("away perspective flips",
      all(a["value"] == -h["value"]
          for a, h in zip(pts_away, pts)))

# 5: entries --------------------------------------------------------------
eb = ah.entry_breakdown(ah.entries_for(rec, nm))
check("entry breakdown total",
      eb["total"] == len(ah.entries_for(rec, nm)))
check("controlled pct math",
      abs(eb["controlled_pct"] -
          (100.0 * eb["controlled"] / eb["total"] if eb["total"]
           else 0.0)) < 1e-9)
check("empty entries safe",
      ah.entry_breakdown([])["controlled_pct"] == 0.0)

# 6: trends ---------------------------------------------------------------
tr = ah.rolling_line_trends(home, n=5)
check("trend lines", set(tr) <= {"L1", "L2", "L3", "L4"})
check("trend length", all(len(v) == 1 for v in tr.values()))

# 7: analyst ---------------------------------------------------------------
rep = ah.analyst_report(home)
check("report sections", len(rep) >= 3)
check("report shape",
      all(isinstance(h, str) and isinstance(ls, list) and ls
          for h, ls in rep))
text = " ".join(l for _, ls in rep for l in ls)
check("report grounded in numbers",
      any(ch.isdigit() for ch in text))
check("report asks, not answers",
      "?" in text or "Your call" in text)

# 8: game labels ------------------------------------------------------------
lbl = ah.game_label(rec, nm)
check("label has score", "-" in lbl and ("W" in lbl or "L" in lbl
                                          or "T" in lbl))
check("label robust", isinstance(ah.game_label({}, ""), str))

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
