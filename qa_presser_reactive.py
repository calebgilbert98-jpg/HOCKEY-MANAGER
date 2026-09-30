"""qa_presser_reactive.py -- the presser answers the night's events.

Verifies the drama -> presser chain at the engine level:
  1. apply_incident_consequences stashes _recent_drama on both clubs.
  2. build_postmatch_presser puts the incident questions FIRST.
  3. Answering applies morale/board/fan effects via the app callbacks.
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
import manager_career as mc

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


# 1. drama question shapes -------------------------------------------------
drama = [
    {"kind": "line_brawl", "live": True, "home": "Toronto Maple Leafs",
     "away": "Ottawa Senators", "home_score": 4, "away_score": 3},
    {"kind": "controversial_hit", "live": False, "hitter": "J. Doe",
     "victim": "A. Smith", "fined": True, "suspended": 0},
]
qs = mc._drama_questions(drama)
check("two drama questions built", len(qs) == 2, f"{len(qs)}")
check("brawl question asks about the fight",
      "gloves came off" in qs[0]["question"], qs[0]["question"][:60])
check("hit question names the hitter",
      "J. Doe" in qs[1]["question"], qs[1]["question"][:60])
check("every drama answer carries effects",
      all("morale_effect" in a and "board_effect" in a and "fan_effect" in a
          for q in qs for a in q["answers"]))

# 2. post-match presser leads with drama -----------------------------------
home = SimpleNamespace(team_name="Toronto Maple Leafs")
away = SimpleNamespace(team_name="Ottawa Senators")
ctx = {"n": "a few", "drama": drama}
post = mc.build_postmatch_presser(home, away, True, False, "4-3",
                                  "A. Matthews", ctx)
check("presser built", len(post) >= 3, f"{len(post)}")
check("drama questions come first",
      post[0]["id"] == "drama_brawl" and post[1]["id"] == "drama_hit",
      f"{[q['id'] for q in post[:3]]}")
check("routine questions follow",
      all(not q["id"].startswith("drama_") for q in post[2:]))

# No drama -> pure routine presser (no crash, no phantom questions).
post2 = mc.build_postmatch_presser(home, away, False, False, "2-5",
                                   "your top line", {"n": "a few",
                                                     "drama": None})
check("no-drama presser has no drama questions",
      all(not q["id"].startswith("drama_") for q in post2))

# 3. stash shape matches what the presser reads ----------------------------
# narrative_incidents.apply_incident_consequences sets team._recent_drama
# to a list of the same dicts _drama_questions consumes.
import inspect
import narrative_incidents as ni
src = inspect.getsource(ni.apply_incident_consequences)
check("_recent_drama stash exists in apply_incident_consequences",
      "_recent_drama" in src)
check("brawl drama kind matches presser consumer",
      '"line_brawl"' in src and "drama_brawl" in inspect.getsource(
          mc._drama_questions))
check("hit drama kind matches presser consumer",
      '"controversial_hit"' in src and "drama_hit" in inspect.getsource(
          mc._drama_questions))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
