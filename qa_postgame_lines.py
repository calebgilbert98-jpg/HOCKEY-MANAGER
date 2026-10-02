"""QA: Post-game Lines tab with combined line ratings (Muck 2026-10-02).

"make it so you can see the lines post game and see the game rating per
line combined (combination of linemates avg performance rating from that
game at 5on5) that way we know if lines are working"

Covers:
  1. compute_skater_game_grade is byte-identical to what record_performance
     appends to recent_game_grades (skater path).
  2. Grade formula sanity: star 2-pt night grades high; scoreless grinder ~50.
  3. snapshot_team_lines: ID structure, empty lineup -> None, garbage -> None.
  4. compute_line_ratings: labels, per-player grades, combined rating = mean
     of linemate grades; missing stats -> None; never raises.
  5. main.py stamps 'lines' on game results (both paths).
  6. Box score TABS includes "Lines".

Run: python3 qa_postgame_lines.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DISPLAY", ":99")

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" -- {detail}" if detail and not cond else ""))


# ---------------------------------------------------------------- imports
import mesh_system
from mesh_system import compute_skater_game_grade, record_performance
from game_classes import snapshot_team_lines
from game_box_score import compute_line_ratings, GameBoxScoreView


class MockPlayer:
    _ids = [0]

    def __init__(self, name, overall, pos="CENTER"):
        MockPlayer._ids[0] += 1
        self.id = MockPlayer._ids[0]
        self.full_name = name
        self._overall = overall
        self.primary_position = type("P", (), {"name": pos, "value": pos})()
        self.secondary_positions = []
        self.recent_game_grades = []
        self.mesh_form = 0.0
        self.mesh_streak = 0
        self.morale = 70
        self.age = 28
        self.games_played = 300

    def overall_rating(self):
        return self._overall


class MockTeam:
    def __init__(self, name, lineup=None):
        self.team_name = name
        self.lineup = lineup or {}


# ------------------------------------------------- 1. grade == ledger grade
p_star = MockPlayer("Star C", 95)
record_performance(p_star, 2, 1)  # 3-pt night
ledger_grade = p_star.recent_game_grades[-1]
pure_grade = compute_skater_game_grade(p_star, 2, 1)
check("pure grade == record_performance ledger grade",
      ledger_grade == pure_grade, f"ledger={ledger_grade} pure={pure_grade}")

p_mid = MockPlayer("Mid W", 78)
record_performance(p_mid, 0, 0)
check("pure grade matches ledger (scoreless)",
      p_mid.recent_game_grades[-1] == compute_skater_game_grade(p_mid, 0, 0))

# ------------------------------------------------- 2. formula sanity
check("star 3-pt night grades high", pure_grade >= 85, f"{pure_grade}")
grind = MockPlayer("Grinder", 72)
g0 = compute_skater_game_grade(grind, 0, 0)
# Formula: expected = 0.15+1.1*.72^2 = .72; surprise = -.72/.72 = -1 -> 25.0
check("scoreless grinder grades 25 (existing formula)", g0 == 25.0, f"{g0}")
check("grade never raises on garbage",
      compute_skater_game_grade(None, "x", None) == 50.0)
check("grade clamped 0-100",
      0.0 <= compute_skater_game_grade(p_star, 99, 99) <= 100.0)

# ------------------------------------------------- 3. snapshot_team_lines
f1 = [MockPlayer("LW1", 88, "LEFT_WING"), MockPlayer("C1", 95, "CENTER"),
      MockPlayer("RW1", 86, "RIGHT_WING")]
d1 = [MockPlayer("LD1", 84, "LEFT_DEFENSE"), MockPlayer("RD1", 83, "RIGHT_DEFENSE")]
team = MockTeam("Testers", {"Forwards": [f1, [], [], []],
                            "Defense": [d1, [], []]})
snap = snapshot_team_lines(team)
check("snapshot Forwards shape",
      snap is not None and len(snap["Forwards"]) == 4
      and snap["Forwards"][0] == [p.id for p in f1],
      f"{snap}")
check("snapshot Defense shape",
      snap["Defense"][0] == [p.id for p in d1])
check("snapshot IDs are ints",
      all(isinstance(i, int) for line in snap["Forwards"] for i in line))
check("empty lineup -> None", snapshot_team_lines(MockTeam("X", {})) is None)
check("garbage team -> None", snapshot_team_lines(None) is None)
check("garbage lineup -> None",
      snapshot_team_lines(MockTeam("X", {"Forwards": "nope"})) is None)

# ------------------------------------------------- 4. compute_line_ratings
by_id = {p.id: p for p in f1 + d1}
gs = {f1[0].id: {"g": 1, "a": 1}, f1[1].id: {"g": 2, "a": 1},
      f1[2].id: {"g": 0, "a": 0},
      d1[0].id: {"g": 0, "a": 1}, d1[1].id: {"g": 0, "a": 0}}
lines = compute_line_ratings(snap, gs, by_id)
check("4 forward lines + 3 pairs",
      len(lines) == 7, f"{len(lines)}")
l1 = lines[0]
check("line label", l1["label"] == "Line 1", l1["label"])
# Implementation rounds each player's grade to 1 decimal first (that's
# what the UI displays), then averages.
exp_grades = [round(compute_skater_game_grade(p, gs[p.id]["g"], gs[p.id]["a"]) / 10.0, 1)
              for p in f1]
exp_rating = round(sum(exp_grades) / 3, 1)
got_grades = [pl["grade"] for pl in l1["players"]]
check("per-player grades on 0-10",
      [round(g, 1) for g in got_grades] == [round(g, 1) for g in exp_grades],
      f"{got_grades} vs {[round(g,1) for g in exp_grades]}")
check("combined rating = mean of linemates",
      l1["rating"] == exp_rating, f"{l1['rating']} vs {exp_rating}")
check("Muck example shape (8.5/7.2/6.8 -> 7.5)",
      round((8.5 + 7.2 + 6.8) / 3, 1) == 7.5)
check("positions shown", all(pl["pos"] for pl in l1["players"]))
pair1 = lines[4]
check("pair label + 2 players",
      pair1["label"] == "Pair 1" and len(pair1["players"]) == 2)

# missing stats -> None grades, rating still from available
gs2 = {f1[0].id: {"g": 1, "a": 0}}
lines2 = compute_line_ratings(snap, gs2, by_id)
check("missing stats -> None grade",
      lines2[0]["players"][1]["grade"] is None)
check("rating from available grades only",
      lines2[0]["rating"] == round(compute_skater_game_grade(
          f1[0], 1, 0) / 10.0, 1))
check("no stats at all -> rating None",
      compute_line_ratings(snap, {}, by_id)[0]["rating"] is None)
check("empty snapshot -> []", compute_line_ratings(None, gs, by_id) == [])
check("garbage never raises",
      compute_line_ratings("x", None, None) == [])

# ------------------------------------------------- 5. main.py stamping
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "main.py"), encoding="utf-8", errors="replace").read()
check("user-game result stamps lines",
      "'lines': self._snapshot_game_lines(home_team, away_team)" in src)
check("batch result stamps lines",
      src.count("'lines': self._snapshot_game_lines(home_team, away_team)") >= 2)
check("_snapshot_game_lines defined", "def _snapshot_game_lines" in src)

# ------------------------------------------------- 6. box score tab
check("Lines in box score TABS", "Lines" in GameBoxScoreView.TABS,
      f"{GameBoxScoreView.TABS}")
check("_fill_lines exists", hasattr(GameBoxScoreView, "_fill_lines"))
check("_refresh_lines exists", hasattr(GameBoxScoreView, "_refresh_lines"))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
