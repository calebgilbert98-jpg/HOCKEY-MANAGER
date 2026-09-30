"""Item 7 follow-up QA: the user ALWAYS picks their club's captains.

Covers the bypass where new-game setup auto-repairs every club before the
user's team is known, plus the claim/pending/flag mechanics. Headless.

QA seed rule: pin random.seed() BEFORE generation.
"""
import random
import sys
import os

random.seed(20260929)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game_classes import PlayerPosition
from main import GameManager

PASS, FAIL = [], []


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


class StubLeague:
    def __init__(self, teams):
        self.teams = teams


def make_team(name, n_skaters=14, n_goalies=2):
    t = StubTeam(name)
    for i in range(n_skaters):
        t.roster.append(StubPlayer(f"{name} Skater {i:02d}",
                                   PlayerPosition.CENTER, leadership=50 + i))
    for i in range(n_goalies):
        t.roster.append(StubPlayer(f"{name} Goalie {i:02d}",
                                   PlayerPosition.GOALIE, leadership=90))
    return t


def fresh_gm(n=4):
    gm = GameManager.__new__(GameManager)
    gm._captaincy_choice_pending = False
    gm.user_team = None
    gm.app = None
    teams = [make_team(f"Club{i}") for i in range(n)]
    gm.league = StubLeague(teams)
    return gm, teams


def letters(t):
    c = [p.full_name for p in t.roster if getattr(p, "captaincy", "") == "C"]
    a = [p.full_name for p in t.roster if getattr(p, "captaincy", "") == "A"]
    return c, a


# --- 1. The wizard bypass: setup loop runs with user_team None, then the
# --- user picks their team via set_user_team.
gm, teams = fresh_gm()
for t in teams:  # what setup_new_game's loop does with user_team=None
    gm._opening_night_captaincy_check(t, None)
check("setup auto-repairs all clubs",
      all(not gm._captaincy_needs_choice(t) for t in teams))
check("setup stamps the auto flag",
      all(getattr(t, "_captaincy_auto_assigned", False) for t in teams))
gm.set_user_team("Club0")
ut = gm.user_team
check("set_user_team arms the pending blocker",
      gm._captaincy_choice_pending is True)
check("auto letters stripped from the human club",
      all(getattr(p, "captaincy", None) in (None, "") for p in ut.roster))
check("other clubs keep their auto-repair",
      all(not gm._captaincy_needs_choice(t) for t in teams[1:]))
check("human club now needs a choice", gm._captaincy_needs_choice(ut))
check("auto flag cleared on claim",
      getattr(ut, "_captaincy_auto_assigned", False) is False)

# --- 2. A human choice (blocker persist path) clears the stamp.
gm2, teams2 = fresh_gm()
t2 = teams2[0]
gm2._ensure_captaincy(t2)
check("ensure stamps flag", getattr(t2, "_captaincy_auto_assigned", False) is True)
sk = [p for p in t2.roster
      if getattr(p, "primary_position", None) != PlayerPosition.GOALIE][:3]
gm2._persist_captaincy_pick(t2, sk[0].full_name, sk[1].full_name, sk[2].full_name)
check("persist clears flag", getattr(t2, "_captaincy_auto_assigned", False) is False)
check("persist writes 1C+2A", not gm2._captaincy_needs_choice(t2))

# --- 3. Load-game: valid, human-chosen letters are NOT disturbed.
gm3, teams3 = fresh_gm()
t3 = teams3[0]
gm3._ensure_captaincy(t3)
t3._captaincy_auto_assigned = False  # human chose in a previous session
before = letters(t3)
gm3.set_user_team(t3.team_name)
check("valid letters survive set_user_team", letters(t3) == before)
check("no blocker armed for valid letters",
      gm3._captaincy_choice_pending is False)

# --- 4. Broken save: no letters at all -> blocker armed, never auto-repaired.
gm4, teams4 = fresh_gm()
gm4.set_user_team(teams4[0].team_name)
check("broken save arms blocker", gm4._captaincy_choice_pending is True)
check("broken save not auto-repaired",
      all(getattr(p, "captaincy", None) in (None, "") for p in teams4[0].roster))

# --- 5. Claim is idempotent.
gm._claim_user_team_captaincy(ut)
check("second claim keeps pending armed", gm._captaincy_choice_pending is True)

# --- 6. Goalie-held letters force a re-pick on claim.
gm6, teams6 = fresh_gm()
t6 = teams6[0]
for p in t6.roster:
    p.captaincy = None
g = next(p for p in t6.roster
         if getattr(p, "primary_position", None) == PlayerPosition.GOALIE)
g.captaincy = "C"
sk6 = [p for p in t6.roster
       if getattr(p, "primary_position", None) != PlayerPosition.GOALIE][:2]
sk6[0].captaincy = "A"
sk6[1].captaincy = "A"
gm6.set_user_team(t6.team_name)
check("goalie C forces re-pick on claim", gm6._captaincy_choice_pending is True)

# --- 7. Claim on None is a safe no-op.
gm7, _ = fresh_gm()
check("claim(None) safe", gm7._claim_user_team_captaincy(None) is False)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
