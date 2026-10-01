# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Bug 5: team talks need a cap/cooldown -- repeated talks must not stack
morale boosts without limit.

Checks: first talk of the day grants full morale; repeats while a talk is
pending grant nothing (but still update the pending record so the latest
tone is what the sim reads); pregame/intermission are independent; the
sim consuming the pending record resets the cooldown; a pending talk from
an older day is stale, not a repeat.
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dressing_room as dr

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}"
          + (f" -- {extra}" if extra and not cond else ""))


class HotRng:
    def uniform(self, a, b):
        return 10.0  # force "landed" (+3 room)


class P:
    _id = 0

    def __init__(self, n):
        P._id += 1
        self.id = P._id
        self.full_name = n
        self.morale = 70


def make_team():
    return SimpleNamespace(team_name="Test", city="Test",
                           roster=[P(f"P{i}") for i in range(4)],
                           staff=[], dressing_room=None)


def morale(team):
    return [p.morale for p in team.roster]


CTX = {"situation": "pregame", "score_state": "tied"}

# 1: first talk grants the full bump
team = make_team()
out1 = dr.give_talk(team, "fired-up", dict(CTX), speaker="coach",
                    rng=HotRng(), day_key="2026-10-01")
check("first talk: full morale bump", morale(team) == [71] * 4, str(morale(team)))
check("first talk: not a repeat", out1.get("repeat") is False)
check("first talk: pending record stored",
      isinstance(team.dressing_room["pregame"], dict))

# 2: spam repeats grant nothing more
for _ in range(11):
    outN = dr.give_talk(team, "fired-up", dict(CTX), speaker="coach",
                        rng=HotRng(), day_key="2026-10-01")
check("11 repeat talks: morale unchanged", morale(team) == [71] * 4,
      str(morale(team)))
check("repeat flagged", outN.get("repeat") is True)
check("repeat note mentions no further lift",
      "no further lift" in outN.get("note", ""))
check("repeat still updates pending tone",
      team.dressing_room["pregame"]["tone"] == "fired-up")

# 3: intermission is an independent situation
outI = dr.give_talk(team, "calm",
                    {"situation": "intermission", "score_state": "tied"},
                    speaker="coach", rng=HotRng(), day_key="2026-10-01")
check("intermission talk: independent, full bump",
      morale(team) == [72] * 4, str(morale(team)))
check("intermission talk: not a repeat", outI.get("repeat") is False)

# 4: sim consuming the record resets the cooldown (next game fresh)
dr.consume_pregame_boost(team)
check("consume clears pending", team.dressing_room["pregame"] is None)
out2 = dr.give_talk(team, "fired-up", dict(CTX), speaker="coach",
                    rng=HotRng(), day_key="2026-10-02")
check("post-game talk: fresh, full bump", morale(team) == [73] * 4,
      str(morale(team)))
check("post-game talk: not a repeat", out2.get("repeat") is False)

# 5: stale pending talk from an older day is not a repeat
team2 = make_team()
dr.give_talk(team2, "fired-up", dict(CTX), speaker="coach",
             rng=HotRng(), day_key="2026-10-01")
outS = dr.give_talk(team2, "fired-up", dict(CTX), speaker="coach",
                    rng=HotRng(), day_key="2026-10-03")
check("stale-day pending: not a repeat", outS.get("repeat") is False)
check("stale-day pending: full bump", morale(team2) == [72] * 4,
      str(morale(team2)))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
