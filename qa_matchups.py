# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA for last-change line matching (matchups.py + wiring). Headless."""
import sys
import types

sys.path.insert(0, '/home/hatch/workspace/HOCKEY-MANAGER')

passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}")


# --- stub shift_engine before matchups imports it lazily -----------------------
_lines = {(True, 1): 2, (True, 2): 2, (False, 1): 1, (False, 2): 1}  # (is_home, team#) -> f_line


class _Shift:
    def __init__(self, f_line):
        self.f_line = f_line


_fake_se = types.ModuleType("shift_engine")


def _get_shift_state(sim, team):
    is_home = team is sim.home_team
    return _Shift(_lines[(is_home, team._tnum)])


_fake_se.get_shift_state = _get_shift_state
sys.modules["shift_engine"] = _fake_se

import matchups as mu


class FakePlayer:
    def __init__(self, ovr):
        self._ovr = ovr

    def overall_rating(self):
        return self._ovr


class FakeTeam:
    def __init__(self, name, tnum, ovrs):
        self.team_name = name
        self._tnum = tnum
        # lineup: F1 = stars, F4 = grinders
        self.lineup = {}
        for ln in range(1, 5):
            for pos in ("LW", "C", "RW"):
                self.lineup[f"F{ln}_{pos}"] = FakePlayer(ovrs[ln - 1])
        for ln in range(1, 4):
            for pos in ("L", "R"):
                self.lineup[f"D{ln}_{pos}"] = FakePlayer(ovrs[ln - 1] - 2)
        self.line_matchups = {"F": [None] * 4, "D": [None] * 3}


class FakeSim:
    def __init__(self, home, away):
        self.home_team = home
        self.away_team = away
        self._matchup_chances = {}


home = FakeTeam("Home", 1, [88, 82, 76, 70])
away = FakeTeam("Away", 2, [86, 80, 74, 68])
sim = FakeSim(home, away)

# --- line strength / edge ---------------------------------------------------------
check("line players found", len(mu.line_players(home, "F", 1)) == 3)
check("strength ~88", abs(mu.line_strength(mu.line_players(home, "F", 1)) - 88) < 0.01)
check("edge bands",
      mu.edge_label(6) == "strong edge" and mu.edge_label(3) == "edge"
      and mu.edge_label(0.5) == "even" and mu.edge_label(-6) == "strongly outmatched"
      and mu.edge_label(None) == "even")

# --- current matchup: home L2 (82) vs away L1 (86) -> outmatched -------------------
cm = mu.current_matchup(sim)
check("current matchup lines", cm["home_line"] == 2 and cm["away_line"] == 1)
check("edge reads outmatched", cm["edge"] == "outmatched")

# --- attribution ---------------------------------------------------------------------
mu.record_chance(sim, home, "high")
mu.record_chance(sim, home, "high")
mu.record_chance(sim, away, "high")
mu.record_chance(sim, home, "medium")
mu.record_goal(sim, home)
mu.record_goal(sim, away)
rep = mu.report(sim)
check("one matchup row", len(rep) == 1)
r = rep[0]
check("hd split home-perspective",
      r["hd_for"] == 2 and r["hd_against"] == 1)
check("goals split", r["goals_for"] == 1 and r["goals_against"] == 1)

# --- verdicts --------------------------------------------------------------------------
sim2 = FakeSim(home, away)
for _ in range(4):
    mu.record_chance(sim2, home, "high")
v = mu.report(sim2)[0]["verdict"]
check("dominant verdict names lines", "your 2" in v and "their 1" in v)
sim3 = FakeSim(home, away)
for _ in range(4):
    mu.record_chance(sim3, away, "high")
v3 = mu.report(sim3)[0]["verdict"]
check("losing verdict advises change", "change it" in v3)

# --- live control -----------------------------------------------------------------------
mu.set_shadow(home, away_line=1, home_line=3, unit="F")
check("shadow set", home.line_matchups["F"][2] == 1)
mu.set_shadow(home, away_line=1, home_line=2, unit="F")  # reassign clears old
check("reassign clears", home.line_matchups["F"][2] is None
      and home.line_matchups["F"][1] == 1)
mu.set_shadow(home, away_line=1, home_line=None, unit="F")
check("clear to auto", home.line_matchups["F"] == [None] * 4)
mu.set_shadow(home, away_line=9, home_line=1)  # invalid ignored
check("invalid ignored", home.line_matchups["F"] == [None] * 4)

mu.preset_shutdown(home)
check("shutdown preset",
      home.line_matchups["F"][2] == 1 and home.line_matchups["D"][0] == 1)
mu.preset_shelter_scorers(home)
check("shelter preset", home.line_matchups["F"][0] == 4)
mu.preset_auto(home)
check("auto preset clears",
      home.line_matchups["F"] == [None] * 4
      and home.line_matchups["D"] == [None] * 3)
d = mu.describe_prefs(home)
check("auto describe empty", d == [])
mu.preset_shutdown(home)
check("describe names shadows",
      any("your 3 shadows their 1" in x for x in mu.describe_prefs(home)))

# --- wiring -------------------------------------------------------------------------------
sim_src = open('/home/hatch/workspace/HOCKEY-MANAGER/simulation.py').read()
check("sim records chances", "_mu_chance(self, attacking_team, quality)" in sim_src)
check("sim records goals", "_mu_goal(self, scoring_team)" in sim_src)
check("sim inits table", "self._matchup_chances = {}" in sim_src)
viz_src = open('/home/hatch/workspace/HOCKEY-MANAGER/pbp_visual_sim.py').read()
check("viz matchup readout", "MATCHUP" in viz_src and "_update_matchup_readout" in viz_src)
check("viz matchups button", '"Matchups", self._toggle_matchup_panel' in viz_src)
check("viz control panel", "LINE MATCHING -- LAST CHANGE IS YOURS" in viz_src)
check("viz attribution table", "WHERE THE CHANCES CAME FROM" in viz_src)
check("viz final verdicts", "Matchups: {_v}." in viz_src)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
