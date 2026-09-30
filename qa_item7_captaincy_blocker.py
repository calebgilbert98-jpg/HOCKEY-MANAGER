# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Item 7 QA: mandatory captaincy user-choice blocker (headless).

Tests the firing logic + validation + persistence without a display:
- blocker fires for the human team at both call sites when not (1C+2A)
- accepts exactly 1C+2As
- rejects 0C, 2C, 1C+1A, 1C+3A, goalie-as-C, goalie-as-A, same-player double
- never fires for AI teams (auto-repair path unchanged)
- already-correct teams pass through without the blocker
- headless _require_captaincy_choice degrades via the pending flag (no crash)

QA seed rule: pin random.seed() BEFORE generation.
"""
import random
import sys
import os

random.seed(20260929)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game_classes import PlayerPosition

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


class StubPlayer:
    _id = 0

    def __init__(self, name, pos, leadership=50):
        StubPlayer._id += 1
        self.id = StubPlayer._id
        self.full_name = name
        self.primary_position = pos
        self.leadership = leadership
        self.captaincy = None

    def overall_rating(self):
        return 78


class StubTeam:
    def __init__(self, name):
        self.team_name = name
        self.league_name = "National Hockey League"
        self.roster = []


def make_player(name, pos, leadership=50):
    return StubPlayer(name, pos, leadership=leadership)


def make_team(n_skaters=14, n_goalies=2):
    t = StubTeam("Test Club")
    for i in range(n_skaters):
        t.roster.append(make_player(f"Skater {i:02d}", PlayerPosition.CENTER,
                                    leadership=50 + i))
    for i in range(n_goalies):
        t.roster.append(make_player(f"Goalie {i:02d}", PlayerPosition.GOALIE,
                                    leadership=90))
    return t


def letters(team):
    c = [p.full_name for p in team.roster
         if getattr(p, "captaincy", "") == "C"]
    a = [p.full_name for p in team.roster
         if getattr(p, "captaincy", "") == "A"]
    return c, a


from main import GameManager

gm = GameManager.__new__(GameManager)  # no heavy __init__
gm._captaincy_choice_pending = False
gm.app = None  # headless: no display

# --- _captaincy_needs_choice ---------------------------------------------
t = make_team()
check("needs_choice: empty letters -> True", gm._captaincy_needs_choice(t))

# exactly 1C + 2A skaters -> False
t.roster[0].captaincy = "C"
t.roster[1].captaincy = "A"
t.roster[2].captaincy = "A"
check("needs_choice: valid 1C+2A -> False", not gm._captaincy_needs_choice(t))

t2 = make_team()
t2.roster[0].captaincy = "C"
t2.roster[1].captaincy = "A"
check("needs_choice: 1C+1A -> True", gm._captaincy_needs_choice(t2))

t3 = make_team()
t3.roster[0].captaincy = "C"
t3.roster[1].captaincy = "C"
t3.roster[2].captaincy = "A"
t3.roster[3].captaincy = "A"
check("needs_choice: 2C -> True", gm._captaincy_needs_choice(t3))

t4 = make_team()
t4.roster[14].captaincy = "C"  # goalie
t4.roster[0].captaincy = "A"
t4.roster[1].captaincy = "A"
check("needs_choice: goalie C -> True", gm._captaincy_needs_choice(t4))

t5 = make_team()
t5.roster[0].captaincy = "C"
t5.roster[14].captaincy = "A"  # goalie alternate
t5.roster[1].captaincy = "A"
check("needs_choice: goalie A -> True", gm._captaincy_needs_choice(t5))

# --- _validate_captaincy_pick ---------------------------------------------
v = make_team()
c_name, a1_name, a2_name = "Skater 00", "Skater 01", "Skater 02"
g_name = "Goalie 00"
check("validate: legal 1C+2A -> None",
      gm._validate_captaincy_pick(v, c_name, a1_name, a2_name) is None)
check("validate: 0C rejected",
      gm._validate_captaincy_pick(v, "", a1_name, a2_name) is not None)
check("validate: 1C+1A rejected",
      gm._validate_captaincy_pick(v, c_name, a1_name, "") is not None)
check("validate: goalie C rejected",
      gm._validate_captaincy_pick(v, g_name, a1_name, a2_name) is not None)
check("validate: goalie A rejected",
      gm._validate_captaincy_pick(v, c_name, g_name, a2_name) is not None)
check("validate: C==A1 rejected",
      gm._validate_captaincy_pick(v, c_name, c_name, a2_name) is not None)
check("validate: A1==A2 rejected",
      gm._validate_captaincy_pick(v, c_name, a1_name, a1_name) is not None)
check("validate: unknown name rejected",
      gm._validate_captaincy_pick(v, "Nobody", a1_name, a2_name) is not None)
err = gm._validate_captaincy_pick(v, g_name, a1_name, a2_name) or ""
check("validate: goalie-C message cites Rule 6.1", "6.1" in err)

# --- _persist_captaincy_pick (manual-tool parity) ---------------------------
p = make_team()
p.roster[5].captaincy = "C"  # stale letters get cleared
gm._persist_captaincy_pick(p, c_name, a1_name, a2_name)
c, a = letters(p)
check("persist: exactly 1C", c == [c_name])
check("persist: exactly 2A", sorted(a) == sorted([a1_name, a2_name]))
check("persist: stale C cleared",
      p.roster[5].captaincy is None)

# --- _require_captaincy_choice headless fallback ---------------------------
h = make_team()  # invalid, headless
check("require headless: returns False, arms pending flag",
      gm._require_captaincy_choice(h) is False
      and gm._captaincy_choice_pending is True)
check("require headless: leaves team untouched (no auto-repair)",
      letters(h) == ([], []))

h2 = make_team()  # valid, headless -> pass-through, no flag
h2.roster[0].captaincy = "C"
h2.roster[1].captaincy = "A"
h2.roster[2].captaincy = "A"
check("require headless valid: True, flag cleared",
      gm._require_captaincy_choice(h2) is True
      and gm._captaincy_choice_pending is False)

# --- _opening_night_captaincy_check: the real shared branch ---------------
# (used by BOTH call sites: setup_new_game and opening night)
fired = []
orig_require = GameManager._require_captaincy_choice
orig_ensure = GameManager._ensure_captaincy


def fake_require(self, team):
    fired.append(("require", team.team_name))
    return False


def fake_ensure(self, team):
    fired.append(("ensure", team.team_name))
    return None


GameManager._require_captaincy_choice = fake_require
GameManager._ensure_captaincy = fake_ensure
try:
    gm2 = GameManager.__new__(GameManager)
    gm2._captaincy_choice_pending = False
    human = make_team()
    human.team_name = "Human Club"
    ai = make_team()
    ai.team_name = "AI Club"
    gm2.user_team = human
    # invalid human -> blocker, not auto-repair
    gm2._opening_night_captaincy_check(human, gm2.user_team)
    # invalid AI -> auto-repair, no blocker
    gm2._opening_night_captaincy_check(ai, gm2.user_team)
    # valid human -> auto-repair pass-through (idempotent), no blocker
    ok = make_team()
    ok.team_name = "Human Club Valid"
    ok.roster[0].captaincy = "C"
    ok.roster[1].captaincy = "A"
    ok.roster[2].captaincy = "A"
    gm2.user_team = ok
    gm2._opening_night_captaincy_check(ok, gm2.user_team)
finally:
    GameManager._require_captaincy_choice = orig_require
    GameManager._ensure_captaincy = orig_ensure

check("firing: human-invalid -> blocker, not auto-repair",
      ("require", "Human Club") in fired
      and ("ensure", "Human Club") not in fired)
check("firing: AI-invalid -> auto-repair, no blocker",
      ("ensure", "AI Club") in fired
      and ("require", "AI Club") not in fired)
check("firing: human-valid -> pass-through, no blocker",
      ("require", "Human Club Valid") not in fired
      and ("ensure", "Human Club Valid") in fired)

# --- AI auto-repair path genuinely unchanged --------------------------------
ai2 = make_team()
nc = orig_ensure(gm, ai2)
c, a = letters(ai2)
check("auto-repair: AI gets 1C+2A skaters",
      len(c) == 1 and len(a) == 2
      and not gm._cap_letter_is_goalie(
          next(p for p in ai2.roster if p.full_name == c[0])))
check("auto-repair: returns new captain name", isinstance(nc, str))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
